import json
from datetime import date

from django.http import HttpResponse, JsonResponse

from api.models import Transaction, Currency, PaymentDetails, BankDetails, BusinessAccount, PersonalAccount

from api.functions import check_valid_request

import numpy as np


def initiate_payment(request):
    # The JSON default data of the response, stored in a dictionary
    response_data = {
        'Status': 400,
        'ErrorCode': None,
        'Comment': ""
    }

    pns_url = ""

    # A function which checks if the response is not empty and can be converted to JSON
    request_data = check_valid_request(request, response_data)

    # If the response included an error code, return the response immediately
    if 'ErrorCode' in request_data:
        return JsonResponse(request_data)

    # Else, we have converted the request into JSON properly, so we can continue

    if request.method == 'POST':
        # Get all the data from the request

        card_number = request_data.get('CardNumber', None)
        cvv = request_data.get('CVV', None)
        expiry = request_data.get('Expiry', None)
        payer_name = request_data.get('CardHolderName', None)
        address = request_data.get('CardHolderAddress', None)
        email = request_data.get('Email', None)
        payee_account_number = request_data.get('PayeeBankAccNum', None)
        payee_sort_code = request_data.get('PayeeBankSortCode', None)
        payee_name = request_data.get('RecipientName', None)
        amount = request_data.get('Amount', None)
        payer_currency_code = request_data.get('PayerCurrencyCode', None)
        payee_currency_code = request_data.get('PayeeCurrencyCode', None)

        if all(value is not None for value in [card_number, cvv, expiry, payer_name,
                                               address, email, payee_account_number,
                                               payee_sort_code, payee_name, amount,
                                               payer_currency_code, payee_currency_code]):
            if amount <= 0:
                response_data.update({
                    'ErrorCode': 1,
                    'Comment': "Error. Amount must be above 0"
                })

            try:
                # check if the payee account exists, both in
                bank_details = BankDetails.objects.get(accountNumber=payee_account_number,
                                                       securityCode=payee_sort_code,
                                                       accountName=payee_name)

                bank_account = BusinessAccount.objects.get(accountNumber=bank_details.accountNumber)

            except BankDetails.DoesNotExist or BusinessAccount.DoesNotExist:
                response_data.update({
                    'ErrorCode': 1,
                    'Comment': "Error. Payee does not exist"
                })

            payment_details = PaymentDetails.objects.filter(cardNumber=card_number,
                                                            securityCode=cvv,
                                                            expiryDate=expiry)

            if payment_details.exists():
                personal_account = PersonalAccount.objects.get(paymentDetails=payment_details.id)

            else:
                payer_id = 0

            payee_id = bank_details.id

            curr_date = str(date.today())

            new_transaction = Transaction(payer=payer_id, payee=payee_id, amount=amount,
                                          currency=payee_currency_code, date=curr_date,
                                          transactionStatus="Initiated")

        data = {'key1': 'value1', 'key2': 'value2'}
        json_data = json.dumps(data)
        response = request.post(pns_url, data=json_data)

        # send info to pns, return it back
    return HttpResponse("hello world")


def initiate_refund(request):
    # The JSON default data of the response, stored in a dictionary
    response_data = {
        'Status': 400,
        'ErrorCode': None,
        'Comment': ""
    }

    # A function which checks if the response is not empty and can be converted to JSON
    request_data = check_valid_request(request, response_data)

    # If the response included an error code, return the response immediately
    if 'ErrorCode' in request_data:
        return JsonResponse(request_data)

    # Else, we have converted the request into JSON properly, so we can continue

    if request.method == 'POST':

        # Gets the values from the request body

        transaction_id = request_data.get('TransactionUUID', None)
        amount = request_data.get('Amount', None)
        currency_code = request_data.get('CurrencyCode', None)

        # Checks if any values have not been supplied
        if all(value is not None for value in [transaction_id, amount, currency_code]):
            try:
                # transaction will already exist from initial payment
                curr_transaction = Transaction.objects.get(id=transaction_id)

                # Sends a request to the PNS

                response = request_refund_pns(request)

                # Gets the status code and the comment
                status = response.get('StatusCode', None)
                comment = response.get('Comment', None)

                if status != 200:
                    response_data['ErrorCode'] = 1  # change to the proper error code
                else:
                    # If the transaction was ok (200) then set the status to refunded
                    curr_transaction.transactionStatus = "Refunded"

                response_data.update({
                    'Status': status,
                    'Comment': comment
                })

            # Will produce the appropriate error code if we can't find the transaction
            except Transaction.DoesNotExist:
                response_data.update({
                    'ErrorCode': 104,
                    'Comment': "Error. Transaction does not exist"
                })

        else:
            # Will produce the appropriate error code if a parameter was not supplied
            response_data.update({
                'ErrorCode': 102,
                'Comment': "Error. One or more parameters were not provided"
            })

    return JsonResponse(response_data)


# done
def initiate_cancellation(request):
    # The JSON default data of the response, stored in a dictionary
    response_data = {
        'ErrorCode': None,
        'Comment': ""
    }

    # A function which checks if the response is not empty and can be converted to JSON
    request_data = check_valid_request(request, response_data)

    # If the response included an error code, return the response immediately
    if 'ErrorCode' in request_data:
        return JsonResponse(request_data, status=400)

    # Else, we have converted the request into JSON properly, so we can continue

    if request.method == 'POST':

        try:
            # Gets the transaction ID and converts it to uint type
            transaction_id = int(request_data.get('TransactionUUID', None))

            cancel_transaction = Transaction.objects.get(id=transaction_id)
            cancel_transaction.transactionStatus = "Cancelled"

            cancel_transaction.save()

            # Updates response with a valid status code and comment
            response_data.update({
                'Comment': "Cancellation Successful"
            })

            return JsonResponse(response_data, status=200)

        except ValueError:
            # The error if there was no transaction ID
            response_data.update({
                'ErrorCode': 102,
                'Comment': "Error. No transaction ID was provided"
            })

        except OverflowError:
            # The error if the transaction ID was not of uint
            response_data.update({
                'ErrorCode': 103,
                'Comment': "Error. Transaction ID needs to be a positive integer"
            })

        # Throws an error if the transaction supplied does not exist
        except Transaction.DoesNotExist:
            response_data.update({
                'ErrorCode': 104,
                'Comment': "Error. Transaction does not exist"
            })

    return JsonResponse(response_data, status=400)


def request_transaction_pns(request):
    return HttpResponse("hello world")


def request_refund_pns(request):
    # The JSON default data of the response, stored in a dictionary
    response_data = {
        'Status': 400,
        'ErrorCode': None,
        'Comment': ""
    }

    pns_url = ""

    # A function which checks if the response is not empty and can be converted to JSON
    request_data = check_valid_request(request, response_data)

    # If the response included an error code, return the response immediately
    if 'ErrorCode' in request_data:
        return JsonResponse(request_data)  # This is actually just the response data

    # Else, we have converted the request into JSON properly, so we can continue

    if request.method == 'POST':

        # Gets the data from the JSON response

        transaction_id = request_data.get('TransactionUUID', None)
        amount = request_data.get('Amount', None)
        currency_code = request_data.get('CurrencyCode', None)

        # If all the values are present then send the response to the PNS
        if all(value is not None for value in [transaction_id, amount, currency_code]):
            response = request.post(pns_url, data=request)

            pns_status = request_data.get('StatusCode', None)

            if pns_status != 200:
                response_data.update({
                    'ErrorCode': 301,
                    'Comment': "Error occurred in the payment network service."
                })
                return JsonResponse(response_data)

            return JsonResponse(response)

        # Updates the response with the error that a parameter is missing
        response_data.update({
            'ErrorCode': 102,
            'Comment': "Error. One or more arguments missing from parameters supplied."
        })

    return JsonResponse(response_data)


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

    # If the response included an error code, return the response immediately
    if 'ErrorCode' in request_data:
        return JsonResponse(request_data, status=400)

    # Else, we have converted the request into JSON properly, so we can continue

    if request.method == 'POST':

        # Get the data from the request
        currency_code_from = request_data.get('CurrencyFrom', None)
        currency_code_to = request_data.get('CurrencyTo', None)
        amount = request_data.get('Amount', None)

        # Check if all values required are present
        if all(value is not None for value in [currency_code_from, currency_code_to, amount]):
            try:
                currency_from = Currency.objects.get(id=currency_code_from)
                currency_to = Currency.objects.get(id=currency_code_to)
                curr_date = str(date.today())  # in y-m-d, may need to change

                # The JSON data containing the data the currency converter API requires
                final_request_data = {
                    'CurrencyFrom': currency_from,
                    'CurrencyTo': currency_to,
                    'Date': curr_date,
                    'Amount': amount
                }

                # Sends a POST request to the currency converter
                # currency_response = request.post(currency_url, data=final_request_data)
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

                response_data.update({
                    'ErrorCode': 201,
                    'Comment': "Error occurred in the currency converter."
                })

            # Gives the appropriate error code if a currency code provided does not exist
            # in the database
            except Currency.DoesNotExist:
                response_data.update({
                    'ErrorCode': 104,
                    'Comment': "Error. One or more currencies provided does not exist"
                })

        # Runs if a parameter is not present
        else:
            # Updates the response with the error that a parameter is missing
            response_data.update({
                'ErrorCode': 102,
                'Comment': "Error. One or more arguments missing from parameters supplied."
            })

    return JsonResponse(response_data, status=400)


codes = {
    100: 'Request body empty.',
    101: 'Request body in incorrect format',
    102: 'Could not find field "{}".',
    103: 'Field {0} is a {1}, when {2} was expected.',
    104: 'Invalid Field(s): {0}',
    201: 'An error occurred with currency conversion.',
    301: 'An error occurred with contacting the Payment Network Service.',
}
