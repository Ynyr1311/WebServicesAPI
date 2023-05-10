import re
from datetime import date, datetime

import requests
from django.db import DatabaseError
from django.http import JsonResponse
from email_validator import validate_email, EmailNotValidError

from api.functions import check_valid_request, error_response
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
                    'Date': curr_date,
                    'Amount': amount
                }

                # Calls the function to get the new currency value
                currency_converter_response = convert_currency(currency_converter_request)

                # If everything is valid, then set the amount to the new value
                if currency_converter_response.status_code == 200:
                    request['amount'] = currency_converter_response["Amount"]

                else:
                    return error_response(response_data, 201)

            # Create a new transaction object, will only save once the payment has gone through

            new_transaction = Transaction(payer=payer_object, payee=payee_object, amount=request['amount'],
                                          currency=payee_currency_code, date=curr_date, transactionStatus="Completed")

            """
            response = request_transaction_pns(request)

            if response.status_code != 200:
                return error_response(response_data, 301)

            """
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
    temp = {  # remove
        'StatusCode': 200,
        'Comment': "Success"
    }

    # A function which checks if the response is not empty and can be converted to JSON
    request_data = check_valid_request(request, response_data)

    if isinstance(request_data, JsonResponse):
        return request_data  # Will be a JSON response of the error

    # Else, we have converted the request into JSON properly, so we can continue

    if request.method == 'POST':

        # Gets the values from the request body
        transaction_id = request_data.get('TransactionUUID', None)
        amount = request_data.get('Amount', None)
        currency_code = request_data.get('CurrencyCode', None)

        if any(value is None for value in (transaction_id, amount, currency_code)):
            return error_response(response_data, 102)

        # Throws a value error if they cannot be converted to the correct types

        if not isinstance(transaction_id, int) or transaction_id < 0:
            # The error if the transaction ID was not of uint
            return error_response(response_data, 103, "Error. Transaction ID needs to be a positive integer")

        if not isinstance(amount, float) or amount <= 0:
            return error_response(response_data, 104, "Error. Amount must be a float value larger than 0")

        try:
            # transaction will already exist from initial payment
            curr_transaction = Transaction.objects.get(id=transaction_id, currency=currency_code)

            if curr_transaction.transactionStatus == "Refunded" or curr_transaction.transactionStatus == "Cancelled":
                return error_response(response_data, 404)
            # Sends a request to the PNS

            # pns_response = request_refund_pns(request)
            pns_response = temp
            # Gets the status code and the comment
            # probably get the error code too
            status = pns_response.get('StatusCode', None)
            comment = pns_response.get('Comment', None)

            # If the transaction was ok (200) then set the status to refunded
            if status == 200:
                curr_transaction.transactionStatus = "Refunded"
                curr_transaction.save()
                response_data['Comment'] = comment  # change to the proper error code
                return JsonResponse(response_data, status=200)

            else:
                return error_response(response_data, 301, comment)

        # Will produce the appropriate error code if we can't find the transaction
        except Transaction.DoesNotExist:
            return error_response(response_data, 402)

    else:
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

    if request.method == 'POST':

        transaction_id = request_data.get('TransactionUUID', None)

        if transaction_id is None:
            return error_response(response_data, 102, "Error. No transaction ID was provided")

        if not isinstance(transaction_id, int) or transaction_id < 0:
            # The error if the transaction ID was not of uint
            return error_response(response_data, 103, "Error. Transaction ID needs to be a positive integer")

        try:
            # Gets the transaction ID and converts it to uint type

            cancel_transaction = Transaction.objects.get(id=transaction_id)

            if cancel_transaction.transactionStatus == "Refunded" or cancel_transaction.transactionStatus == "Cancelled":
                return error_response(response_data, 404)

            cancel_transaction.transactionStatus = "Cancelled"

            cancel_transaction.save()

            # Updates response with a valid status code and comment
            response_data['Comment'] = "Cancellation Successful"
            return JsonResponse(response_data, status=200)

        # Throws an error if the transaction supplied does not exist
        except Transaction.DoesNotExist:
            return error_response(response_data, 402)

    else:
        return error_response(response_data, 105)


def request_transaction_pns(request):
    # The JSON default data of the response, stored in a dictionary
    response_data = {
        'ErrorCode': None,
        'Comment': ""
    }
    temp = {
        'StatusCode': 200,
        'Comment': "Success"
    }

    pns_url = "..."

    # A function which checks if the response is not empty and can be converted to JSON
    request_data = check_valid_request(request, response_data)

    if isinstance(request_data, JsonResponse):
        return request_data  # Will be a JSON response of the error

    if request.method == 'POST':

        request_data.pop('PayerCurrencyCode')
        request_data.pop('RecipientName')
        request_data.pop('Email')


        request_data['HolderName'] = request_data.pop('CardHolderName')
        request_data['BillingAddress'] = request_data.pop('CardHolderAddress')
        request_data['CurrencyCode'] = request_data.pop('PayeeCurrencyCode')
        request_data['AccountNumber'] = request_data.pop('PayeeBankAccNum')
        request_data['Sort-Code'] = request_data.pop('PayeeBankSortCode')

        #response = requests.post(pns_url, data=pns_request_data)
        response = temp

        #if response.status_code != 200:
            #return error_response(response_data, 301)
        if temp['StatusCode'] != 200:
            return error_response(response_data, 301)

        response_data['Comment'] = "PNS Payment Successful"
        return JsonResponse(response_data, status=200)
    else:
        return error_response(response_data, 105)


def request_refund_pns(request):
    # The JSON default data of the response, stored in a dictionary
    response_data = {
        'ErrorCode': None,
        'Comment': ""
    }

    pns_url = "..."

    if request.method == 'POST':

        response = requests.post(pns_url, data=request)

        if response.status_code != 200:
            return error_response(response_data, 301)

        response_data['Comment'] = "PNS Refund Successful"
        return JsonResponse(response_data, status=200)
    else:
        return error_response(response_data, 105)


def convert_currency(request):
    # The JSON default data of the response, stored in a dictionary
    response_data = {
        'ErrorCode': None,
        'Comment': "",
        'Amount': None
    }
    temp = {  # DELETE LATER
        'StatusCode': 200,
        'ErrorCode': None,
        'Comment': "Success",
        'Amount': 200
    }

    # The URL to access the currency converter endpoint
    currency_url = 'endpoint'

    # A function which checks if the response is not empty and can be converted to JSON
    request_data = check_valid_request(request, response_data)

    if isinstance(request_data, JsonResponse):
        return request_data  # Will be a JSON response of the error

    # Else, we have converted the request into JSON properly, so we can continue

    if request.method == 'POST':


        # Get the data from the request
        currency_code_from = request_data.get('CurrencyFrom', None)
        currency_code_to = request_data.get('CurrencyTo', None)
        amount = request_data.get('Amount', None)
        date = request_data.get('Date', None)


        # Sends a POST request to the currency converter
        # currency_response = request.post(currency_url, data=request)
        currency_response = temp
        # Gets the status code of the request, if it was valid, then extract the new amount,
        # else, produce the correct error code
        curr_converter_status = currency_response.get('StatusCode', None)

        if curr_converter_status == 200:
            response_data.update({
                'ErrorCode': None,
                'Comment': currency_response.get('Comment'),
                'Amount': currency_response.get('Amount')
            })
            return JsonResponse(response_data, status=200)

        return error_response(response_data, 201)
    else:
        return error_response(response_data, 105)

