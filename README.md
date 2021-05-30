# KMyMoney's XML to hledger/beancount journal file converter

This script converts transactions listed in a KMyMoney's XML file to transactions printed in the hledger/beancount's
journal format. Multiple transaction splits *are also supported*.

## Use

    cat [inputfile].kmy | gunzip > [inputfile].xml
    python kmymoney2ledgers.py [inputfile].xml

then output is written into file [inputfile].xml.journal or [inputfile].xml.beancount. The output file name can be
specified using "-o" option:

    python kmymoney2ledgers.py [-o outputfile] [inputfile].xml

Help:

    python3 kmymoney2ledgers.py [-o <outputfile>] <inputfile>

    Input flags:
        -b --beancount                                       use beancount output format (otherwise default is hledger)
        -r --replace-destination-account-commodity           replace destination account commodity (currency) with source
                                                             account commodity. No currency conversion is performed.
        -s --use-currency-symbols                            replace some of the currency codes specified in ISO 4217 with
                                                             corresponding unicode currency symbols (experimental)


## Use cases

- switching to plain text accounting with hledger/beancount,
- using generated journal file for creating multicurrency financial reports in hledger/beancount.

 This tool solves a problem of preparing financial reports in KMyMoney when multiple currencies are used (expenses in vacations, moving to another country).
 KMyMoney does not support multicurrency expense categories. The currency of an expense category is specified during the category's creation.

 Scenarios:
 1) All expense categories are opened in the base currency during the KMyMoney file creation.
    Default behavior since people usually spend money in the base currency.
 2) Some or all expense categories are duplicated in other currencies.
    This has to be done manually for every expense category, e.g. "public transport" category has to be
    created in USD, EUR etc. and named properly using suffixes in the names. The problem with this approach is
    that expenses in the same category but different categories cannot be summed up.

 Default behavior of KMyMoney for scenario 1:

 All expense transactions in a foreign currency account will have a converted value of
 the transaction amount in the base currency for the destination account (expense category).
 KMyMoney will always ask about the conversion rate between foreign and base currency.

 Scenario 2 is impractical, since expenses are spread among different currencies and cannot be summed up.

 With this tool one can stop worrying about the currency of the expense category and ignore conversion rate,
 since this information will not be used when "-r" flag is specified.

 ## Multicurrency example:

 Summarize yearly income and expenses by categories at depth level 2 starting with year 2019 by converting all earnings/spendings
 in different foreign currencies into Euros where the exchange rate is inferred from the purchase of foreign currencies in
 the "money" (asset) accounts. With an exception of equity accounts, before spending some amount US Dollars on food,
 a larger amount of US Dollars should be bought using the money in the base currency (EUR, replaced by €).

    cat Finances.kmy | gunzip > Finances.xml
    python3 kmymoney2ledgers.py -r -s Finances.xml
    hledger -f Finances.xml.journal balance --flat -Y -b 2019 --change --depth 2 --invert -X € --infer-value Income Expense

 Perform the same operation, but do not convert foreign currency expenses into the base currency. The food expenses in
 this case will be shown separately in EUR and USD.

    cat Finances.kmy | gunzip > Finances.xml
    python3 kmymoney2ledgers.py -r -s Finances.xml
    hledger -f Finances.xml.journal balance --flat -Y -b 2019 --change --depth 2 Income Expense

 Beancount example with fava frontend:

    pip install fava
    cat Finances.kmy | gunzip > Finances.xml
    python3 kmymoney2ledgers.py -br -o Finances.beancount Finances.xml
    fava Finances.beancount
    # In internet browser open http://localhost:5000
