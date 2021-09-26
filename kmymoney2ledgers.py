#! /usr/bin/python3
# KMyMoney's XML to hledger/beancount's journal file converter
# License: GPL v3.0
# Author: Altynbek Isabekov

import xml.etree.ElementTree as ET
import sys
import getopt
import string

# Account types are defined in:
# Repo: https://invent.kde.org/office/kmymoney
# File: kmymoney/mymoney/mymoneyenums.h
# fmt: off
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
# fmt: on

CurrencyDict = {
    "EUR": "€",
    "TRL": "₺",
    "USD": "$",
    "CZK": "Kč",
    "HRK": "kn",
    "CRC": "₡",
    "OMR": "ر.ع.",
    "HUF": "Ft",
    "PLN": "zł",
    "KZT": "₸",
    "KGS": "С",
    "GEL": "₾",
    "INR": "₹",
    "NGN": "₦",
    "GBP": "£",
}

money_accounts = [
    AccountTypes[k]
    for k in [
        "Checkings",
        "Savings",
        "Cash",
        "CreditCard",
        "Asset",
        "Liability",
        "Equity",
    ]
]
categories = [AccountTypes[k] for k in ["Income", "Expense"]]

AccountRenaming = {"Asset": "Assets", "Liability": "Liabilities", "Expense": "Expenses"}

# fmt: off
def print_help():
    print(f"python3 {sys.argv[0]} [-o <outputfile>] <inputfile>\n")
    print(
        "Input flags:\n\
    -b --beancount                                    use beancount output format (otherwise default is hledger)\n\
    -r --replace-destination-account-commodity        replace destination account commodity (currency) with source\n\
                                                      account commodity. No currency convesion is performed.\n\
    -s --use-currency-symbols                         replace some of the currency codes specified in ISO 4217 with\n\
                                                      corresponding unicode currency symbols (experimental)\n\
    "
    )
    return
# fmt: on


def remove_spec_chars(text):
    table = str.maketrans(dict.fromkeys(string.punctuation + " ", "-"))
    ntxt = text.translate(table)
    if ntxt[0] == "-":
        return ntxt[1:]
    else:
        return ntxt


def traverse_account_hierarchy_backwards(accounts, acnt_id, to_use_beancount):
    if accounts[acnt_id]["parentaccount"] == "":
        acnt_name = accounts[acnt_id]["name"]
        if acnt_name in AccountRenaming.keys():
            acnt_name = AccountRenaming[acnt_name]
        return acnt_name
    else:
        parent_acnt_name = traverse_account_hierarchy_backwards(
            accounts, accounts[acnt_id]["parentaccount"], to_use_beancount
        )
    if to_use_beancount:
        acnt_name = remove_spec_chars(accounts[acnt_id]["name"])
    else:
        acnt_name = accounts[acnt_id]["name"]
    return f"{parent_acnt_name}:{acnt_name}"


def traverse_account_hierarchy_forwards(root, parent, acnt, to_use_beancount):
    if acnt.tag == "ACCOUNT":
        if to_use_beancount:
            if acnt.attrib["name"] in list(AccountRenaming.keys()):
                acnt_name = AccountRenaming[acnt.attrib["name"]]
            else:
                acnt_name = acnt.attrib["name"]
            acnt_name = remove_spec_chars(acnt_name)
        else:
            acnt_name = acnt.attrib["name"]

        opening_date = acnt.attrib["opened"]
        if opening_date == "":
            opening_date = "1900-01-01"

        closing_date = ""
        if len(acnt.findall("./KEYVALUEPAIRS/PAIR/[@key='mm-closed']")) != 0:
            closing_date = acnt.attrib["lastmodified"]

        if not to_use_beancount:
            opening_date = opening_date.replace("-", "/")
            closing_date = closing_date.replace("-", "/")

        subaccounts = acnt.findall("./SUBACCOUNTS/SUBACCOUNT")

    elif acnt.tag == "KMYMONEY-FILE":
        acnt_name = ""
        subaccounts = acnt.findall("./ACCOUNTS/ACCOUNT/[@parentaccount='']")

    if (parent == "") and (acnt.tag == "ACCOUNT"):
        account_lines = ""
        new_parent = f"{acnt_name}"
    elif parent != "":
        account_lines = (
            f"{opening_date} open  {parent}:{acnt_name}  ; {acnt.attrib['id']}\n"
        )
        if closing_date != "":
            account_lines += (
                f"{closing_date} close {parent}:{acnt_name}  ; {acnt.attrib['id']}\n"
            )
        new_parent = f"{parent}:{acnt_name}"
    else:
        account_lines = ""
        new_parent = f"{acnt_name}"

    if len(subaccounts) != 0:
        for subacnt_id in list(subaccounts):
            if subacnt_id.tag == "SUBACCOUNT":
                subacnt = root.findall(
                    f"./ACCOUNTS/ACCOUNT/[@id='{subacnt_id.attrib['id']}']"
                )[0]
            else:
                subacnt = subacnt_id

            subacnt_lines = traverse_account_hierarchy_forwards(
                root, new_parent, subacnt, to_use_beancount
            )
            account_lines += subacnt_lines
    return account_lines


def print_account_info(root, to_use_beancount):
    account_lines = traverse_account_hierarchy_forwards(
        root, "", root, to_use_beancount
    )
    return "; Accounts\n" + account_lines


def print_operating_currency(root):
    base_currency = root.findall("./KEYVALUEPAIRS/PAIR/[@key='kmm-baseCurrency']")[
        0
    ].attrib["value"]
    return f'option "operating_currency" "{base_currency}"\n'


def print_currency_prices(root, to_use_beancount, to_use_currency_symbols):
    price_lines = "; Currency prices"
    for k in root.findall("./PRICES/PRICEPAIR"):
        if k.attrib["from"] != k.attrib["to"]:
            if to_use_currency_symbols & (k.attrib["from"] in CurrencyDict.keys()):
                cmdty_from = CurrencyDict[k.attrib["from"]]
            else:
                cmdty_from = k.attrib["from"]

            if to_use_currency_symbols & (k.attrib["to"] in CurrencyDict.keys()):
                cmdty_to = CurrencyDict[k.attrib["to"]]
            else:
                cmdty_to = k.attrib["to"]

            price_lines += f"\n;==== {cmdty_from} to {cmdty_to} =====\n"

            for m in k:
                if to_use_beancount:
                    price_lines += (
                        f'{m.attrib["date"]} price {cmdty_from}'
                        f' {eval(m.attrib["price"]):.4f} {cmdty_to} ; source:'
                        f' {m.attrib["source"]}\n'
                    )
                else:
                    price_lines += (
                        f'P {m.attrib["date"].replace("-", "/")} {cmdty_from}'
                        f' {eval(m.attrib["price"]):.4f} {cmdty_to} ; source:'
                        f' {m.attrib["source"]}\n'
                    )
    return price_lines


def use_currency_symbol_if_exists(currency):
    if currency in CurrencyDict.keys():
        currency = CurrencyDict[currency]
    return currency


def print_transactions(
    transactions,
    payees,
    accounts,
    tags_dict,
    to_keep_destination_account_commodity,
    to_use_beancount,
    to_use_currency_symbols,
):
    for k in accounts.keys():
        accounts[k]["fullname"] = traverse_account_hierarchy_backwards(
            accounts, k, to_use_beancount
        )
    # Process all transactions
    all_lines = ""
    n_transactions = len(transactions)
    for i, item in enumerate(transactions):
        if (i % 100 == 1) or (i == n_transactions - 1):
            print(f"Processing transaction {i+1}/{n_transactions}")
        txn_id = item.attrib["id"]
        splits = list(item.findall("./SPLITS")[0])
        date = item.attrib["postdate"]
        if not to_use_beancount:
            date = date.replace("-", "/")
        txn_commodity = item.attrib["commodity"]

        # Payee in all splits should be the same, choose the first one
        acnt_id = splits[0].attrib["account"]
        acnt_type = int(accounts[acnt_id]["type"])
        payee_id = splits[0].attrib["payee"]
        if payee_id != "":
            payee = payees[payee_id]["name"]
        elif acnt_type == AccountTypes["Equity"]:
            payee = accounts[acnt_id]["name"]
        else:
            payee = ""
        payee = payee.replace('"', "'") if to_use_beancount else payee

        # Tags at transaction level
        if len(splits) == 2:
            txn_tags = splits[0].findall("./TAG")
            if len(txn_tags) >= 1:
                tags = " ; "
                for k in txn_tags:
                    tags += f"{tags_dict[k.attrib['id']]}:, "
                tags = tags[:-1]
            else:
                tags = ""
        else:
            tags = "" # There can be tags at split (posting) level though

        # Transaction header
        all_lines += f"; {txn_id}\n"
        all_lines += f'{date} * "{payee}" ; {payee_id}; {tags}\n'

        for spl in splits:
            acnt_id = spl.attrib["account"]
            acnt_type = int(accounts[acnt_id]["type"])
            acnt_name = accounts[acnt_id]["fullname"]
            acnt_currency = accounts[acnt_id]["currency"]
            value = eval(spl.attrib["value"])
            shares = eval(spl.attrib["shares"])
            memo = spl.attrib["memo"]
            memo = memo.replace('"', "'") if to_use_beancount else memo
            memo = memo.replace("\n", "\\n")

            # Tags at split (posting) level
            spl_tags = spl.findall("./TAG")
            if len(spl_tags) >= 1:
                tags = " ; "
                for k in spl_tags:
                    tags += f"{tags_dict[k.attrib['id']]}:, "
                tags = tags[:-2]
            else:
                tags = ""

            if to_use_currency_symbols & (acnt_currency in CurrencyDict.keys()):
                acnt_currency = use_currency_symbol_if_exists(acnt_currency)
                txn_commodity = use_currency_symbol_if_exists(txn_commodity)

            cond_1 = txn_commodity == acnt_currency
            cond_2 = (
                (not cond_1)
                & (not to_keep_destination_account_commodity)
                & (acnt_type in categories)
            )
            if cond_1 or cond_2:
                # Destination account currency is replaced with source account currency and the destination amount
                # is set to the negated source amount when:
                # * source and destination accounts have the same currency, the destination account can be either
                #   a "money" account or an "expense category",
                # * source is a "money" account and destination is an "expense category" and the flag
                # "to_keep_destination_account_commodity" is set to false.
                all_lines += (
                    f"   {acnt_name}  {value:.4f} {txn_commodity}{tags}"
                )
            else:
                # Keep the destination account currency as it is specified in the KMyMoney transaction when:
                # * source is a "money" account and destination is an "expense category" and it was specified in
                #   the input argument in the flag "to_keep_destination_account_commodity" to do so,
                # * some amount of a foreign currency is bought, so conversion is necessary, since both source and
                #   destination accounts are "money" accounts (inverse of cond_1).
                all_lines += (
                    f"   {acnt_name}  {shares:.4f} {acnt_currency} @@ {abs(value):.4f}"
                    f" {txn_commodity}{tags}"
                )
            all_lines += f"\n" if memo == "" else f"   ; {memo}\n"
        all_lines += "\n"
    return "; Transactions\n" + all_lines


def main(argv):
    try:
        opts, args = getopt.getopt(
            argv[1:],
            "hbrso:",
            [
                "help",
                "replace-destination-account-commodity",
                "beancount",
                "use-currency-symbols",
                "output=",
            ],
        )
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
            outputfile = f"{inputfile}.beancount"
        else:
            outputfile = f"{inputfile}.journal"

    # ============== PARSING XML ================
    parser = ET.XMLParser(encoding="utf-8")
    tree = ET.parse(inputfile, parser=parser)
    root = tree.getroot()

    # ============== OPERATING CURRENCY =========
    if to_use_beancount:
        header = 'option "title" "Personal Finances"\n'
        header += print_operating_currency(root)
        header += 'plugin "beancount.plugins.implicit_prices"\n'
    else:
        header = ""

    # ============== ACCOUNTS ===================
    accounts = dict()
    for k in list(root.findall("./ACCOUNTS")[0]):
        accounts[k.attrib["id"]] = k.attrib
    account_lines = (
        print_account_info(root, to_use_beancount) if to_use_beancount else ""
    )

    # ============== PAYEES =====================
    payees = dict()
    for k in list(root.findall("./PAYEES")[0]):
        payees[k.attrib["id"]] = k.attrib

    # =============== TAGS ======================
    tags = dict()
    for k in root.findall("./TAGS/TAG"):
        tags[k.attrib["id"]] = k.attrib["name"]

    # ============== TRANSACTIONS ===============
    transactions = list(root.findall("./TRANSACTIONS")[0])
    txn_lines = print_transactions(
        transactions,
        payees,
        accounts,
        tags,
        to_keep_destination_account_commodity,
        to_use_beancount,
        to_use_currency_symbols,
    )

    # ============== PRICES =====================
    price_lines = print_currency_prices(root, to_use_beancount, to_use_currency_symbols)

    # ============== OUTPUT =====================
    out_file_id = open(outputfile, "w")
    out_file_id.writelines(
        header + "\n" + account_lines + "\n" + txn_lines + "\n" + price_lines
    )
    out_file_id.close()
    return


if __name__ == "__main__":
    main(sys.argv)
