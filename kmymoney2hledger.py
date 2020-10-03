#! /usr/bin/python3
# KMyMoney's XML to hledger's journal file converter
# License: GPL v3.0
# Author: Altynbek Isabekov

import xml.etree.ElementTree as ET
import sys
import getopt

# Account types are defined in:
# Repo: https://invent.kde.org/office/kmymoney
# File: kmymoney/mymoney/mymoneyenums.h
AccountTypes = {
    "Unknown": 0,              # For error handling
    "Checkings": 1,            # Standard checking account
    "Savings": 2,              # Typical savings account
    "Cash": 3,                 # Denotes a shoe-box or pillowcase stuffed with cash
    "CreditCard": 4,           # Credit card accounts
    "Loan": 5,                 # Loan and mortgage accounts (liability)
    "CertificateDep": 6,       # Certificates of Deposit
    "Investment": 7,           # Investment account
    "MoneyMarket": 8,          # Money Market Account
    "Asset": 9,                # Denotes a generic asset account.*/
    "Liability": 10,           # Denotes a generic liability account.*/
    "Currency": 11,            # Denotes a currency trading account.
    "Income": 12,              # Denotes an income account
    "Expense": 13,             # Denotes an expense account
    "AssetLoan": 14,           # Denotes a loan (asset of the owner of this object)
    "Stock": 15,               # Denotes an security account as sub-account for an investment
    "Equity": 16               # Denotes an equity account e.g. opening/closing balance
}

CurrencyDict = {'EUR': '€', 'TRL': '₺', 'USD': '$', 'CZK': 'Kč', 'HRK': 'kn', 'CRC': '₡', 'OMR': 'ر.ع.',
                'HUF': 'Ft', 'PLN': 'zł', 'KZT': '₸', 'KGS': 'С', 'GEL': '₾', 'INR': '₹', 'NGN': '₦', 'GBP': '£'}

money_accounts = [AccountTypes[k] for k in ['Checkings', 'Savings', 'Cash', 'CreditCard', 'Asset', 'Liability', 'Equity']]
categories = [AccountTypes[k] for k in ['Income', 'Expense']]


def print_help():
    print("python3 {} -i <inputfile> [-o <outputfile>]\n".format(sys.argv[0]))
    print('Input flags:\n\
    -r --replace-destination-account-commodity           replace destination account commodity (currency) with source\n\
                                                         account commodity. No currency convesion is performed.\n\
    -s --use-currency-symbols                            replace some of the currency codes specified in ISO 4217 with\n\
                                                         corresponding unicode currency symbols (experimental)\n\
    ')
    return


def traverse_account_hierarchy(accounts, acnt_id):
    if accounts[acnt_id]['parentaccount'] == "":
        return accounts[acnt_id]['name']
    else:
        parent_acnt_name = traverse_account_hierarchy(accounts, accounts[acnt_id]['parentaccount'])
    return "{}:{}".format(parent_acnt_name, accounts[acnt_id]['name'])


def main(argv):
    try:
        opts, args = getopt.getopt(argv[1:], "hrso:",
                                   ["help", "replace-destination-account-commodity", "use-currency-symbols", "output="])
    except getopt.GetoptError:
        print_help()
        sys.exit(2)

    # Default flags
    to_keep_destination_account_commodity = True
    to_use_currency_symbols = False

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print_help()
            sys.exit()
        elif opt in ("-r", "--replace-destination-account-commodity"):
            to_keep_destination_account_commodity = False
        elif opt in ("-s", "--use-currency-symbols"):
            to_use_currency_symbols = True
        elif opt in ("-o", "--output"):
            outputfile = arg

    if len(args) == 1:
        inputfile = args[0]

    if not ("outputfile" in vars()):
        outputfile = "{}.journal".format(inputfile)

    parser = ET.XMLParser(encoding="utf-8")
    tree = ET.parse(inputfile, parser=parser)
    root = tree.getroot()

    accounts = dict()
    for k in list(root.findall("./ACCOUNTS")[0]):
        accounts[k.attrib['id']] = k.attrib

    payees = dict()
    for k in list(root.findall("./PAYEES")[0]):
        payees[k.attrib['id']] = k.attrib

    # Process all transactions
    all_lines = ""
    transactions = list(root.findall('./TRANSACTIONS')[0])
    n_transactions = len(transactions)
    for i, item in enumerate(transactions):
        if i % 100 == 1:
            print("Processing transaction {}/{}".format(i, n_transactions))
        trans_id = item.attrib['id']
        splits = list(item.findall('./SPLITS')[0])
        payee_id = splits[0].attrib['payee']
        if payee_id != '':
            memo = payees[payee_id]['name']
        else:
            memo = ''
        # Source account
        src = splits[0].attrib
        acnt_src_id = src['account']
        acnt_src_type = int(accounts[acnt_src_id]['type'])
        acnt_src_name = traverse_account_hierarchy(accounts, acnt_src_id)
        acnt_src_currency = accounts[acnt_src_id]['currency']
        src_amount = eval(src['price']) * eval(src['value'])

        if to_use_currency_symbols & (acnt_src_currency in CurrencyDict.keys()):
            acnt_src_currency = CurrencyDict[acnt_src_currency]

        # Destination account
        if len(list(splits)) == 2:
            dst = splits[1].attrib
            acnt_dst_id = dst['account']
            acnt_dst_type = int(accounts[acnt_dst_id]['type'])
            acnt_dst_name = traverse_account_hierarchy(accounts, acnt_dst_id)
            acnt_dst_currency = accounts[acnt_dst_id]['currency']
            dst_amount = eval(dst['value']) / eval(dst['price'])
            if to_use_currency_symbols & (acnt_dst_currency in CurrencyDict.keys()):
                acnt_dst_currency = CurrencyDict[acnt_dst_currency]
        else:
            print('No destination for source:')
            print("{} ({}) {}\n   {}  {} {:.4f}\n\n".format(date, trans_id, memo,
                                                            acnt_src_name, acnt_src_currency, src_amount))
            continue

        cond_1 = acnt_src_currency == acnt_dst_currency
        cond_2 = (not cond_1) & (not to_keep_destination_account_commodity) & (acnt_src_type in money_accounts) & (acnt_dst_type in categories)
        if cond_1 or cond_2:
            # Destination account currency is replaced with source account currency and the destination amount
            # is set to the negated source amount when:
            # * source and destination accounts have the same currency, the destination account can be either a "money"
            #   account or an "expense category",
            # * source is a "money" account and destination is an "expense category" and the flag
            # "to_keep_destination_account_commodity" is set to false.
            all_lines += "{} ({}) {}\n   {}  {} {:.4f}\n   {}  {} {:.4f}\n\n".format(date, trans_id, memo,
                          acnt_src_name, acnt_src_currency, src_amount,
                          acnt_dst_name, acnt_src_currency, -src_amount)
        else:
            # Keep the destination account currency as it is specified in the KMyMoney transaction when:
            # * source is a "money" account and destination is an "expense category" and it was specified in the input
            #   argument in the flag "to_keep_destination_account_commodity" to do so,
            # * some amount of a foreign currency is bought, so conversion is necessary, since both source and
            #   destination accounts are "money" accounts (inverse of cond_1).
            all_lines += "{} ({}) {}\n   {}  {} {:.4f} @@ {} {:.4f}\n   {}  {} {:.4f}\n\n".format(date, trans_id, memo,
                        acnt_src_name, acnt_src_currency, src_amount, acnt_dst_currency, abs(dst_amount),
                        acnt_dst_name, acnt_dst_currency, dst_amount)

    out_file_id = open(outputfile, "w")
    out_file_id.writelines(all_lines)
    out_file_id.close()
    return


if __name__ == "__main__":
    main(sys.argv)
