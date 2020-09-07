#! /usr/bin/python3
import xml.etree.ElementTree as ET
import sys


def traverse_account_hierarchy(accounts, acnt_id):
    if accounts[acnt_id]['parentaccount'] == "":
        return accounts[acnt_id]['name']
    else:
        parent_acnt_name = traverse_account_hierarchy(accounts, accounts[acnt_id]['parentaccount'])
    return "{}:{}".format(parent_acnt_name, accounts[acnt_id]['name'])


def main(argv):
    inputfile = argv[0]
    outputfile = "{}.journal".format(inputfile)

    parser = ET.XMLParser(encoding="utf-8")
    tree = ET.parse(inputfile, parser=parser)
    root = tree.getroot()

    accounts = dict()
    for k in list(root.iter('ACCOUNTS'))[0]:
        accounts[k.attrib['id']] = k.attrib

    payees = dict()
    for k in list(root.iter('PAYEES'))[0]:
        payees[k.attrib['id']] = k.attrib

    splits = list(list(root.iter('SPLITS')))

    # Process all transactions
    all_lines = ""
    for i, item in enumerate(list(list(root.iter('TRANSACTIONS'))[0])):
        date = item.attrib['postdate'].replace('-', '/')
        trans_id = item.attrib['id']

        payee_id = splits[i][0].attrib['payee']
        if payee_id != '':
            memo = payees[payee_id]['name']
        else:
            memo = ''
        # Source
        src = splits[i][0].attrib
        acnt_src_id = src['account']
        acnt_src_name = traverse_account_hierarchy(accounts, acnt_src_id)
        acnt_src_currency = accounts[acnt_src_id]['currency']
        src_amount = eval(src['price']) * eval(src['value'])

        # Destination
        if len(list(splits[i])) == 2:
            dst = splits[i][1].attrib
            acnt_dst_id = dst['account']
            acnt_dst_name = traverse_account_hierarchy(accounts, acnt_dst_id)
            acnt_dst_currency = accounts[acnt_dst_id]['currency']
            dst_amount = eval(dst['value']) / eval(dst['price'])
        else:
            print('No destination for source:')
            print("{} ({}) {}\n   {}  {} {:.4f}\n\n".format(date, trans_id, memo,
                                                            acnt_src_name, acnt_src_currency, src_amount))
            continue

        if acnt_src_currency != acnt_dst_currency:
            # Currency conversion
            all_lines += "{} ({}) {}\n   {}  {} {:.4f} @@ {} {:.4f}\n   {}  {} {:.4f}\n\n".format(date, trans_id, memo,
                        acnt_src_name, acnt_src_currency, src_amount, acnt_dst_currency, abs(dst_amount),
                        acnt_dst_name, acnt_dst_currency, dst_amount)
        else:
            all_lines += "{} ({}) {}\n   {}  {} {:.4f}\n   {}  {} {:.4f}\n\n".format(date, trans_id, memo,
                                                 acnt_src_name, acnt_src_currency, src_amount,
                                                 acnt_dst_name, acnt_dst_currency, dst_amount)

    out_file_id = open(outputfile, "w")
    out_file_id.writelines(all_lines)
    out_file_id.close()
    return


if __name__ == "__main__":
    main(sys.argv[1:])
