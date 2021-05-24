#! /usr/bin/python3
# KMyMoney's XML to hledger's journal file converter
# License: GPL v3.0
# Author: Altynbek Isabekov

import xml.etree.ElementTree as ET
import sys
import getopt
import string

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

AccountRenaming = {"Asset": "Assets", "Liability": "Liabilities", "Expense": "Expenses"}

def print_help():
    print("python3 {} [-o <outputfile>] <inputfile>\n".format(sys.argv[0]))
    print('Input flags:\n\
    -b --beancount                                       use beancount output format (otherwise default is hledger)\n\
    -r --replace-destination-account-commodity           replace destination account commodity (currency) with source\n\
                                                         account commodity. No currency convesion is performed.\n\
    -s --use-currency-symbols                            replace some of the currency codes specified in ISO 4217 with\n\
                                                         corresponding unicode currency symbols (experimental)\n\
    ')
    return


def remove_spec_chars(text):
    table = str.maketrans(dict.fromkeys(string.punctuation + " ", "-"))
    ntxt = text.translate(table)
    if ntxt[0] == "-":
        return ntxt[1:]
    else:
        return ntxt


def traverse_account_hierarchy_backwards(accounts, acnt_id, to_use_beancount):
    if accounts[acnt_id]['parentaccount'] == "":
        acnt_name = accounts[acnt_id]['name']
        if acnt_name in AccountRenaming.keys():
            acnt_name = AccountRenaming[acnt_name]
        return acnt_name
    else:
        parent_acnt_name = traverse_account_hierarchy_backwards(accounts, accounts[acnt_id]['parentaccount'], to_use_beancount)
    if to_use_beancount == True:
        acnt_name = remove_spec_chars(accounts[acnt_id]['name'])
    else:
        acnt_name = accounts[acnt_id]['name']
    return "{}:{}".format(parent_acnt_name, acnt_name)


def traverse_account_hierarchy_forwards(root, parent, acnt, to_use_beancount):
    if acnt.tag == "ACCOUNT":
        if to_use_beancount == True:
            if (acnt.attrib['name'] in list(AccountRenaming.keys())):
                acnt_name = AccountRenaming[acnt.attrib['name']]
            else:
                acnt_name = acnt.attrib['name']
            acnt_name = remove_spec_chars(acnt_name)
        else:
            acnt_name = acnt.attrib['name']
        opening_date = acnt.attrib["opened"]
        if opening_date == "":
            opening_date = "1900-01-01"
        closing_date = ""
        if len(acnt.findall("./KEYVALUEPAIRS/PAIR/[@key='mm-closed']")) != 0:
            closing_date = acnt.attrib["lastmodified"]
        if to_use_beancount == False:
            opening_date = opening_date.replace('-', '/')
            closing_date = closing_date.replace('-', '/')
        subaccounts = acnt.findall("./SUBACCOUNTS/SUBACCOUNT")
    elif acnt.tag == "KMYMONEY-FILE":
        acnt_name = ""
        subaccounts = acnt.findall("./ACCOUNTS/ACCOUNT/[@parentaccount='']")

    if (parent == "") and (acnt.tag == "ACCOUNT"):
        account_lines = ""
        new_parent = "{}".format(acnt_name)
    elif parent != "":
        account_lines = "{} open  {}:{}\n".format(opening_date, parent, acnt_name)
        if closing_date != "":
            account_lines += "{} close {}:{}\n".format(closing_date, parent, acnt_name)
        new_parent = "{}:{}".format(parent, acnt_name)
    else:
        account_lines = ""
        new_parent = "{}".format(acnt_name)

    if len(subaccounts) != 0:
        for subacnt_id in list(subaccounts):
            if subacnt_id.tag == "SUBACCOUNT":
                subacnt = root.findall("./ACCOUNTS/ACCOUNT/[@id='{}']".format(subacnt_id.attrib['id']))[0]
            else:
                subacnt = subacnt_id
            subacnt_lines = traverse_account_hierarchy_forwards(root, new_parent, subacnt, to_use_beancount)
            account_lines += subacnt_lines
    return  account_lines


def print_account_info(root, to_use_beancount):
    account_lines = traverse_account_hierarchy_forwards(root, '', root, to_use_beancount)
    return account_lines


def print_operating_currency(root):
    base_currency = root.findall("./KEYVALUEPAIRS/PAIR/[@key='kmm-baseCurrency']")[0].attrib['value']
    return "option \"operating_currency\" \"{}\"\n".format(base_currency)


def print_transactions(transactions, payees, accounts, to_keep_destination_account_commodity, to_use_beancount, to_use_currency_symbols):
    # Process all transactions
    all_lines = ""
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
        date = item.attrib['postdate']
        if to_use_beancount == False:
            date = date.replace('-', '/')
        # Source account
        src = splits[0].attrib
        acnt_src_id = src['account']
        acnt_src_type = int(accounts[acnt_src_id]['type'])
        acnt_src_name = traverse_account_hierarchy_backwards(accounts, acnt_src_id, to_use_beancount)
        acnt_src_currency = accounts[acnt_src_id]['currency']
        src_amount = eval(src['price']) * eval(src['shares'])

        if to_use_currency_symbols & (acnt_src_currency in CurrencyDict.keys()):
            acnt_src_currency = CurrencyDict[acnt_src_currency]

        # Destination account
        if len(list(splits)) == 2:
            dst = splits[1].attrib
            acnt_dst_id = dst['account']
            acnt_dst_type = int(accounts[acnt_dst_id]['type'])
            acnt_dst_name = traverse_account_hierarchy_backwards(accounts, acnt_dst_id, to_use_beancount)
            acnt_dst_currency = accounts[acnt_dst_id]['currency']
            dst_amount = eval(dst['shares'])
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
            if to_use_beancount == True:
                all_lines += "{} {} \"{}\"\n   {}  {:.4f} {}\n   {}  {:.4f} {}\n\n".format(date, "*", memo.replace('"', '\''),
                          acnt_src_name, src_amount, acnt_src_currency,
                          acnt_dst_name, -src_amount, acnt_src_currency)
            else:
                all_lines += "{} ({}) {}\n   {}  {} {:.4f}\n   {}  {}  {:.4f}\n\n".format(date, trans_id, memo,
                          acnt_src_name, acnt_src_currency, src_amount,
                          acnt_dst_name, acnt_src_currency, -src_amount)
        else:
            # Keep the destination account currency as it is specified in the KMyMoney transaction when:
            # * source is a "money" account and destination is an "expense category" and it was specified in the input
            #   argument in the flag "to_keep_destination_account_commodity" to do so,
            # * some amount of a foreign currency is bought, so conversion is necessary, since both source and
            #   destination accounts are "money" accounts (inverse of cond_1).
            if to_use_beancount == True:
                all_lines += "{} {} \"{}\"\n   {}  {:.4f} {} @@ {:.4f} {}\n   {}  {:.4f} {} \n\n".format(date, "*", memo.replace('"', '\''),
                        acnt_src_name, src_amount, acnt_src_currency, abs(dst_amount), acnt_dst_currency,
                        acnt_dst_name, dst_amount, acnt_dst_currency)
            else:
                all_lines += "{} ({}) {}\n   {}  {} {:.4f} @@ {} {:.4f}\n   {}  {} {:.4f}\n\n".format(date, trans_id, memo,
                        acnt_src_name, acnt_src_currency, src_amount, acnt_dst_currency, abs(dst_amount),
                        acnt_dst_name, acnt_dst_currency, dst_amount)
    return all_lines


def main(argv):
    try:
        opts, args = getopt.getopt(argv[1:], "hbrso:",
                                   ["help", "replace-destination-account-commodity", "beancount", "use-currency-symbols", "output="])
    except getopt.GetoptError:
        print_help()
        sys.exit(2)

    # Default flags
    to_keep_destination_account_commodity = True
    to_use_currency_symbols = False
    to_use_beancount = False

    for opt, arg in opts:
        if opt in ("-h", "--help"):
            print_help()
            sys.exit()
        elif opt in ("-b", "--beancount"):
            to_use_beancount = True
        elif opt in ("-r", "--replace-destination-account-commodity"):
            to_keep_destination_account_commodity = False
        elif opt in ("-s", "--use-currency-symbols"):
            to_use_currency_symbols = True
        elif opt in ("-o", "--output"):
            outputfile = arg

    if len(args) == 1:
        inputfile = args[0]

    if not ("outputfile" in vars()):
        if to_use_beancount == True:
            outputfile = "{}.beancount".format(inputfile)
        else:
            outputfile = "{}.journal".format(inputfile)

    # ============== PARSING XML ================
    parser = ET.XMLParser(encoding="utf-8")
    tree = ET.parse(inputfile, parser=parser)
    root = tree.getroot()

    # ============== OPERATING CURRENCY =========
    if to_use_beancount == True:
        header = print_operating_currency(root)
    else:
        header = ""

    # ============== ACCOUNTS ===================
    accounts = dict()
    for k in list(root.findall("./ACCOUNTS")[0]):
        accounts[k.attrib['id']] = k.attrib

    if to_use_beancount == True:
        account_lines = print_account_info(root, to_use_beancount)
    else:
        account_lines = ""

    # ============== PAYEES =====================
    payees = dict()
    for k in list(root.findall("./PAYEES")[0]):
        payees[k.attrib['id']] = k.attrib

    # ============== TRANSACTIONS ===============
    transactions = list(root.findall('./TRANSACTIONS')[0])
    txn_lines = print_transactions(transactions, payees, accounts, to_keep_destination_account_commodity,
                                   to_use_beancount, to_use_currency_symbols)

    # ============== OUTPUT =====================
    out_file_id = open(outputfile, "w")
    out_file_id.writelines(header + "\n" + account_lines + "\n" + txn_lines)
    out_file_id.close()
    return


if __name__ == "__main__":
    main(sys.argv)
