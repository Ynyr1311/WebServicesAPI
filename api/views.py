import json
import re
from datetime import date, datetime

import requests
from django.db import DatabaseError
from django.http import JsonResponse
from email_validator import validate_email, EmailNotValidError

from api.functions import check_valid_request, error_response, error_response_external
from api.models import Transaction, PaymentDetails, BankDetails, BusinessAccount, PersonalAccount


def initiate_payment(request):
    # The JSON default data of the response, stored in a dictionary
    response_data = {
        'ErrorCode': None,
        'Comment': ""
    }

    # Regex for checking the card, cvv and currency code values
    card_regex = "^[0-9]{16}$"
    three_digit_regex = "^[0-9]{3}$"
    sort_code_regex = "^[0-9]{6}$"
    account_number_regex = "^[0-9]{1,8}$"

    # A function which checks if the response is not empty and can be converted to JSON
    request_data = check_valid_request(request, response_data)

    if isinstance(request_data, JsonResponse):
        return request_data  # Will be a JSON response of the error

    # Else, we have converted the request into JSON properly, so we can continue

    if request.method == 'POST':

        # Get all the data from the request, the above is all the data we do additional checks on
        card_number = request_data.get('CardNumber', None)
        cvv = request_data.get('CVV', None)
        payer_currency_code = request_data.get('PayerCurrencyCode', None)
        payee_currency_code = request_data.get('PayeeCurrencyCode', None)
        amount = request_data.get('Amount', None)
        expiry = request_data.get('Expiry', None)
        payee_account_number = request_data.get('PayeeBankAccNum', None)
        payee_sort_code = request_data.get('PayeeBankSortCode', None)

        # Compiling the regex strings
        compiled_three_digit_regex = re.compile(three_digit_regex)
        compiled_card_regex = re.compile(card_regex)
        compiled_sort_code_regex = re.compile(sort_code_regex)
        compiled_account_number_regex = re.compile(account_number_regex)

        # Card Number cannot be none when trying to remove whitespaces or hyphens, so we need
        # To throw this error before
        if not isinstance(card_number, str):
            return error_response(response_data, 102, "Error. Card number is not present.")

        # Removes any whitespace or hyphens from a card number if it is present
        card_number = re.sub('[^0-9a-zA-Z]+', '', card_number)

        # Returns an error response if the card number doesn't comply to the regex
        if not re.search(compiled_card_regex, card_number):
            return error_response(response_data, 104, "Error. Card number is not in the correct format")

        # Returns an error response if either currency code is not present
        if not isinstance(payer_currency_code, str) or not isinstance(payee_currency_code, str):
            return error_response(response_data, 102, "Error. A Currency code for the payer and payee need to be "
                                                      "supplied")

        # Returns an error response if either currency code doesn't comply to the regex
        if not re.search(compiled_three_digit_regex, payer_currency_code) \
                or not re.search(compiled_three_digit_regex, payee_currency_code):
            return error_response(response_data, 104, "Error. One or more of the currency codes provided are not in "
                                                      "the correct format")

        # Returns an error response if the cvv wasn't included or doesn't comply to the regex
        if not isinstance(cvv, str) or not re.search(compiled_three_digit_regex, cvv):
            return error_response(response_data, 104, "Error. CVV is either not present or not in the correct "
                                                      "format.")

        # Returns an error response if the account number was not included or doesn't comply to the regex
        if not isinstance(payee_account_number, str) \
                or not re.search(compiled_account_number_regex, payee_account_number):
            return error_response(response_data, 104, "Error. Account number is either not present or not in the "
                                                      "correct format.")

        # Sort code cannot be none when trying to remove whitespaces or hyphens, so we need
        # To throw this error before
        if not isinstance(payee_sort_code, str):
            return error_response(response_data, 102, "Error. Payee Sort Code is not present.")

        # Removes any whitespace or hyphens from a sort code if it is present
        payee_sort_code = re.sub('[^0-9a-zA-Z]+', '', payee_sort_code)

        # Returns an error response if the Sort code doesn't comply to the regex
        if not re.search(compiled_sort_code_regex, payee_sort_code):
            return error_response(response_data, 104, "Error. Sort Code is not in the correct format")

        # Checks if the amount is a float and greater than 0
        if not isinstance(amount, float) or amount <= 0:
            return error_response(response_data, 104, "Error. Amount must be a float value larger than 0")

        # Gets the rest of the details from the request

        payer_name = request_data.get('CardHolderName', None)
        address = request_data.get('CardHolderAddress', None)
        email = request_data.get('Email', None)
        payee_name = request_data.get('RecipientName', None)

        # Checks if all the other values are in the request ( We've already checked this for the previous
        # Values)
        if all(value is not None for value in
               [expiry, payer_name, address, email, payee_account_number, payee_sort_code, payee_name]):

            try:
                # Checks if the email is valid using the email-validator library
                validate_email(email)

                # Attempts to change the expiry to a date format
                expiry = datetime.strptime(expiry, '%Y-%m-%d').date()
                curr_date = date.today()

                # Checks if the expiry date is either today or has already passed
                if expiry <= curr_date:
                    return error_response(response_data, 104, "Error. Card has expired.")

                # check if the payee account exists, both in the bank details and the business account tables
                bank_details = BankDetails.objects.get(accountNumber=payee_account_number,
                                                       sortCode=payee_sort_code,
                                                       accountName=payee_name)

                payee_object = BusinessAccount.objects.get(accountNumber=bank_details.accountNumber)

                # Check if the both the card details exist in the db, along with the personal account with those
                # Details
                payment_id = PaymentDetails.objects.get(cardNumber=card_number, securityCode=cvv,
                                                        expiryDate=expiry).paymentId

                payer_object = PersonalAccount.objects.get(paymentDetails=payment_id, fullName=payer_name, email=email)

            # If the email is not valid
            except EmailNotValidError:
                return error_response(response_data, 104, "Error. Email provided is not in the correct format.")

            # If an error occurs whilst trying to convert the expiry from a string to a date
            except ValueError:
                return error_response(response_data, 104, "Error. Date is not valid. (Needs to be a real date in "
                                                          "YYYY-MM-DD Format)")

            # If the bank details provided do not exist
            except BankDetails.DoesNotExist:
                return error_response(response_data, 107)

            # If the bank details provided exist, but there's not a business account with the same account number
            except BusinessAccount.DoesNotExist:
                return error_response(response_data, 109)

            # If the payment details provided don't exist in the db
            except PaymentDetails.DoesNotExist:
                return error_response(response_data, 106)

            # If the payment details exist, but there is not an account linked with those payment details
            except PersonalAccount.DoesNotExist:
                return error_response(response_data, 108)

            # If the connection to the database fails
            except DatabaseError:
                return error_response(response_data, 401)

            # If both currency codes are not the same then we need to convert the amount
            if payer_currency_code != payee_currency_code:

                # Creates the request body
                currency_converter_request = {
                    'CurrencyFrom': payer_currency_code,
                    'CurrencyTo': payee_currency_code,
                    'Date': str(curr_date),
                    'Amount': amount
                }
                json_object = json.dumps(currency_converter_request)
                # Calls the function to get the new currency value (converts the request to JSON too)
                currency_converter_response = convert_currency(json_object)

                # If everything is valid, then set the amount to the new value
                if currency_converter_response.status_code == 200:
                    request['amount'] = currency_converter_response["Amount"]
                    amount = request['amount']

                else:
                    return currency_converter_response

            # Create a new transaction object, will only save once the payment has gone through

            new_transaction = Transaction(payer=payer_object, payee=payee_object, amount=amount,
                                          currency=payee_currency_code, date=curr_date, transactionStatus="Completed")

            pns_response = request_transaction_pns(request)

            if pns_response.status_code != 200:
                return pns_response

            # Save the transaction now that it has been completed
            new_transaction.save()
            response_data["Comment"] = "Payment Successfully Completed"

            return JsonResponse(response_data, status=200)
        else:
            return error_response(response_data, 102)

    else:
        return error_response(response_data, 105)


def initiate_refund(request):
    # The JSON default data of the response, stored in a dictionary
    response_data = {
        'ErrorCode': None,
        'Comment': ""
    }

    # The regex to check the currency code is valid
    currency_code_regex = "^[0-9]{3}$"
    compiled_currency_code_regex = re.compile(currency_code_regex)

    # A function which checks if the response is not empty and can be converted to JSON
    request_data = check_valid_request(request, response_data)

    if isinstance(request_data, JsonResponse):
        return request_data  # Will be a JSON response of the error

    # Else, we have converted the request into JSON properly, so we can continue

    if request.method == 'POST':

        # Gets the values from the request body
        transaction_id = request_data.get('TransactionUUID', None)
        amount = request_data.get('Amount', None)  # The amount they're being refunded
        currency_code = request_data.get('CurrencyCode', None)

        # Throws an error if any values are not present
        if any(value is None for value in (transaction_id, amount, currency_code)):
            return error_response(response_data, 102)

        # Throws a value error if they cannot be converted to the correct types

        if not isinstance(transaction_id, int) or transaction_id < 0:
            # The error if the transaction ID was not of uint
            return error_response(response_data, 103, "Error. Transaction ID needs to be a positive integer")

        if not isinstance(amount, float) or amount <= 0:
            return error_response(response_data, 104, "Error. Amount must be a float value larger than 0")

        if not re.search(compiled_currency_code_regex, currency_code):
            return error_response(response_data, 104, "Error. The currency code provided is not in the correct format")

        try:
            # transaction will already exist from initial payment
            curr_transaction = Transaction.objects.get(id=transaction_id)

            if curr_transaction.transactionStatus == "Refunded" or curr_transaction.transactionStatus == "Cancelled":
                return error_response(response_data, 404)

            # When refunding, we create a new transaction detailing how much was refunded. These have a status of
            # 'Refund Transaction'. We give a more specific error for this.
            if curr_transaction.transactionStatus == "Refund Transaction":
                return error_response(response_data, 404,
                                      "Error. The transaction ID provided is for a refund transaction")

            # If the currency that we want a refund in is not the same that was carried out for the transaction
            if curr_transaction.currency != currency_code:
                # Creates the request body
                currency_converter_request = {
                    'CurrencyFrom': currency_code,
                    'CurrencyTo': curr_transaction.currency,
                    'Date': date.today(),
                    'Amount': amount
                }

                # Calls the function to get the new currency value
                currency_converter_response = convert_currency(currency_converter_request)

                # If everything is valid, then set the amount to the new value
                if currency_converter_response.status_code == 200:
                    amount = currency_converter_response["Amount"]

                else:
                    # Returns the valid error code and message
                    return currency_converter_response

            if amount > curr_transaction.amount:
                return error_response(response_data, 104, "Error. The amount requested was greater than the total fee "
                                                          "of your booking.")

            # Sends a request to the PNS
            pns_response = request_refund_pns(request)

            # If the transaction was ok, then set the status to refunded, and create a new transaction detailing how
            # much was refunded (which is in a negative value).
            if pns_response.status_code == 200:
                new_transaction = Transaction(payer=curr_transaction.payer, payee=curr_transaction.payee,
                                              amount=-amount,
                                              currency=curr_transaction.currency, date=curr_transaction.date,
                                              transactionStatus="Refund Transaction")

                curr_transaction.transactionStatus = "Refunded"
                curr_transaction.save()
                new_transaction.save()
                response_data['Comment'] = "Refund Successful"  # change to the proper error code
                return JsonResponse(response_data, status=200)
            else:
                # Else it will pass along the error message from the PNS along with our relevant error code
                return pns_response

        # Will produce the appropriate error code if we can't find the transaction
        except Transaction.DoesNotExist:
            return error_response(response_data, 402)

    else:
        # If it isn't a POST request
        return error_response(response_data, 105)


def initiate_cancellation(request):
    # The JSON default data of the response, stored in a dictionary
    response_data = {
        'ErrorCode': None,
        'Comment': ""
    }

    # A function which checks if the response is not empty and can be converted to JSON
    request_data = check_valid_request(request, response_data)

    if isinstance(request_data, JsonResponse):
        return request_data  # Will be a JSON response of the error

    # Else, we have converted the request into JSON properly, so we can continue

    # Checks if it is a POST method
    if request.method == 'POST':

        transaction_id = request_data.get('TransactionUUID', None)

        # Checks a TransactionUUID was provided
        if transaction_id is None:
            return error_response(response_data, 102, "Error. No transaction ID was provided")

        # Checks the transaction ID is a positive integer
        if not isinstance(transaction_id, int) or transaction_id < 0:
            return error_response(response_data, 103, "Error. Transaction ID needs to be a positive integer")

        try:
            # Finding the transaction we want to cancel
            cancel_transaction = Transaction.objects.get(id=transaction_id)

            # Return an error if the transaction is already refunded or cancelled
            if cancel_transaction.transactionStatus == "Refunded" or cancel_transaction.transactionStatus == "Cancelled":
                return error_response(response_data, 404)

            # When refunding, we create a new transaction detailing how much was refunded. These have a status of
            # 'Refund Transaction'. We give a more specific error for this.
            if cancel_transaction.transactionStatus == "Refund Transaction":
                return error_response(response_data, 404,
                                      "Error. The transaction ID provided is for a refund transaction")

            # Updating and saving the transaction status
            cancel_transaction.transactionStatus = "Cancelled"
            cancel_transaction.save()

            # Updates response with a valid status code and comment
            response_data['Comment'] = "Cancellation Successful"
            return JsonResponse(response_data, status=200)

        # Throws an error if the transaction we're trying to find using the ID supplied does not exist
        except Transaction.DoesNotExist:
            return error_response(response_data, 402)

    else:
        # Return an error if it's not a POST request
        return error_response(response_data, 105)


def request_transaction_pns(request):
    # The JSON default data of the response, stored in a dictionary
    response_data = {
        'ErrorCode': None,
        'Comment': ""
    }

    # The URL of the PNS
    pns_url = " http://samshepherd.eu.pythonanywhere.com/pns/initiatetransactionpns/"

    # A function which checks if the response is not empty and can be converted to JSON
    request_data = check_valid_request(request, response_data)

    if isinstance(request_data, JsonResponse):
        return request_data  # Will be a JSON response of the error, otherwise we continue

    # Remove the arguments the PNS doesn't need
    request_data.pop('PayerCurrencyCode')
    request_data.pop('RecipientName')
    request_data.pop('Email')

    # Change the name of some keys to match what the PNS expects
    request_data['HolderName'] = request_data.pop('CardHolderName')
    request_data['BillingAddress'] = request_data.pop('CardHolderAddress')
    request_data['CurrencyCode'] = request_data.pop('PayeeCurrencyCode')
    request_data['AccountNumber'] = request_data.pop('PayeeBankAccNum')
    request_data['Sort-Code'] = request_data.pop('PayeeBankSortCode')

    # Send a POST request with this data to the PNS
    pns_response = requests.post(pns_url, data=request_data)

    # Return our error code and their comment if the request was not OK
    if pns_response.status_code != 200:
        return error_response_external(pns_response, response_data, 301)

    # Else, return an OK response
    response_data['Comment'] = "PNS Payment Successful"
    return JsonResponse(response_data, status=200)


def request_refund_pns(request):
    # The JSON default data of the response, stored in a dictionary
    response_data = {
        'ErrorCode': None,
        'Comment': ""
    }

    # URL of the PNS
    pns_url = " http://samshepherd.eu.pythonanywhere.com/pns/initiatetransactionpns/"

    # We don't alter any data, and have already checked it in initiate_refund, so we can pass it on.
    pns_response = requests.post(pns_url, data=request)

    # Returns our error code and their comment if request was not 200
    if pns_response.status_code != 200:
        return error_response_external(pns_response, response_data, 301)

    # Else, the refund was successful
    response_data['Comment'] = "PNS Refund Successful"

    return JsonResponse(response_data, status=200)


def convert_currency(request):
    # The JSON default data of the response, stored in a dictionary
    response_data = {
        'ErrorCode': None,
        'Comment': "",
        'Amount': None
    }

    # The URL to access the currency converter endpoint
    currency_url = ' http://samshepherd.eu.pythonanywhere.com/currency/convert/'

    # A function which checks if the response is not empty and can be converted to JSON

    # Sends a POST request to the currency converter
    currency_response = requests.post(currency_url, data=request)

    # Gets the status code of the request, if it was valid, then extract the new amount,
    # else, produce the correct error code
    print(currency_response.status_code)
    if currency_response.status_code != 200:
        return error_response_external(currency_response, response_data, 201)

    # We get the amount from the response body and ensure we send it back.
    response_body = json.loads(currency_response.text)
    print(response_body)

    response_data['Amount'] = response_body['Amount']
    response_data['Comment'] = "Conversion Successful"

    return JsonResponse(response_data, status=200)
