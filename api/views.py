from datetime import date, datetime

from django.http import JsonResponse
from email_validator import validate_email, EmailNotValidError

from api.functions import check_valid_request, error_response
from api.models import Transaction, Currency, PaymentDetails, BankDetails, BusinessAccount, PersonalAccount


def initiate_payment(request):
    # The JSON default data of the response, stored in a dictionary
    response_data = {
        'ErrorCode': None,
        'Comment': ""
    }

    currency_converter_request = {
        'CurrencyFrom': 0,
        'CurrencyTo': 0,
        'Amount': 0
    }

    # A function which checks if the response is not empty and can be converted to JSON
    request_data = check_valid_request(request, response_data)

    if isinstance(request_data, JsonResponse):
        return request_data  # Will be a JSON response of the error

    # Else, we have converted the request into JSON properly, so we can continue

    if request.method == 'POST':
        # Get all the data from the request, the above is all the non string data
        cvv = request_data.get('CVV', None)
        payer_currency_code = request_data.get('PayerCurrencyCode', None)
        payee_currency_code = request_data.get('PayeeCurrencyCode', None)
        amount = request_data.get('Amount', None)
        expiry = request_data.get('Expiry', None)

        """
        # Checks all non-string values can be cast correctly
        if not isinstance(cvv, int) or cvv > 999 or cvv < :
            # The error if the transaction ID was not of uint
            return error_response(response_data, "Error. CVV sent is not an int")
        """

        if not isinstance(amount, float) or amount <= 0:
            return error_response(response_data, 104, "Error. Amount must be a float value larger than 0")

        card_number = request_data.get('CardNumber', None)
        payer_name = request_data.get('CardHolderName', None)
        address = request_data.get('CardHolderAddress', None)
        email = request_data.get('Email', None)

        payee_account_number = request_data.get('PayeeBankAccNum', None)
        payee_sort_code = request_data.get('PayeeBankSortCode', None)
        payee_name = request_data.get('RecipientName', None)

        if all(value is not None for value in [card_number, expiry, payer_name,
                                               address, email, payee_account_number,
                                               payee_sort_code, payee_name]):

            # change this bit
            try:
                v = validate_email(email)
                email1 = v["email"]
                print(v)
                print(email1)

                expiry = datetime.strptime(expiry, '%Y-%m-%d').date()
                curr_date = date.today()

                if expiry <= curr_date:
                    return error_response(response_data, 104, "Error. Card has expired.")

            except EmailNotValidError:
                return error_response(response_data, 104, "Error. Email provided is not in the correct format.")

            except ValueError:
                return error_response(response_data, 104, "Error. Date is not in YYYY-MM-DD Format")

            try:
                # check if the payee account exists, both in the bank details and the business account tables
                bank_details = BankDetails.objects.get(accountNumber=payee_account_number,
                                                       sortCode=payee_sort_code,
                                                       accountName=payee_name)

                payee_object = BusinessAccount.objects.get(accountNumber=bank_details.accountNumber)

                payment_id = PaymentDetails.objects.get(cardNumber=card_number, securityCode=cvv,
                                                        expiryDate=expiry).paymentId

                payer_object = PersonalAccount.objects.get(accountNumber=payment_id)

            except BankDetails.DoesNotExist or BusinessAccount.DoesNotExist:
                return error_response(response_data, 104, "Error. Payee does not exist")

            except PaymentDetails.DoesNotExist or PersonalAccount.DoesNotExist:
                return error_response(response_data, 104, "Error. Payer does not exist")
                pass

            if payer_currency_code != payee_currency_code:
                currency_converter_request.update({
                    'CurrencyFrom': payer_currency_code,
                    'CurrencyTo': payee_currency_code,
                    'Date': curr_date,
                    'Amount': amount
                })
                currency_converter_response = convert_currency(currency_converter_request)

                if currency_converter_response.status_code == 200:
                    currency_converter_response["Amount"] = amount

                else:
                    return error_response(currency_converter_response, 201)

            new_transaction = Transaction(payer=payer_object, payee=payee_object, amount=amount,
                                          currency=payee_currency_code, date=curr_date, transactionStatus="Initiated")

            new_transaction.save()

            # send their account number
            # payer_object.accountNumber

            """
            response = request_transaction_pns(request)

            if response.status_code != 200:
                return error_response(response_data, 301)

            else:
                return JsonResponse(response_data, status=200)
            """
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

        if any(transaction_id, amount, currency_code) is None:
            return error_response(response_data, 102, "Error. No transaction ID was provided")

        if not isinstance(transaction_id, int) or transaction_id < 0:
            # The error if the transaction ID was not of uint
            return error_response(response_data, 103, "Error. Transaction ID needs to be a positive integer")

        if not isinstance(amount, float) or amount <= 0:
            return error_response(response_data, 104, "Error. Amount must be a float value larger than 0")

        """
        # Throws a value error if they cannot be converted to the correct types
        except ValueError:  # might need to change this
            if any(value is None for value in [transaction_id, amount, currency_code]):
                error_response(response_data, 102)
            else:
                error_response(response_data, 103)
        """
        try:
            # transaction will already exist from initial payment
            curr_transaction = Transaction.objects.get(id=transaction_id)

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
                error_response(response_data, 301, comment)

        # Will produce the appropriate error code if we can't find the transaction
        except Transaction.DoesNotExist:
            error_response(response_data, 104, "Error. Transaction does not exist")

    else:
        error_response(response_data, 105)

    return JsonResponse(response_data, status=400)


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
            cancel_transaction.transactionStatus = "Cancelled"

            cancel_transaction.save()

            # Updates response with a valid status code and comment
            response_data['Comment'] = "Cancellation Successful"
            return JsonResponse(response_data, status=200)

        # Throws an error if the transaction supplied does not exist
        except Transaction.DoesNotExist:
            return error_response(response_data, 104, "Error. Transaction does not exist")

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

    pns_status = 400  # Default to a bad request

    pns_url = "..."

    # A function which checks if the response is not empty and can be converted to JSON
    request_data = check_valid_request(request, response_data)

    if isinstance(request_data, JsonResponse):
        return request_data  # Will be a JSON response of the error

    if request.method == 'POST':

        pns_request_data = {
            'CardNumber': None,
            'Expiry': None,
            'CVV': None,
            'HolderName': None,
            'BillingAddress': None,
            'Amount': None,
            'CurrencyCode': None,
            'AccountNumber': None,
            'Sort-Code': None,
            'RecipientName': None
        }

        request_data['HolderName'] = request_data.pop('CardHolderName')
        request_data['BillingAddress'] = request_data.pop('CardHolderAddress')
        request_data['CurrencyCode'] = request_data.pop('PayeeCurrencyCode')
        request_data['AccountNumber'] = request_data.pop('PayeeBankAccNum')
        request_data['Sort-Code'] = request_data.pop('PayeeBankSortCode')

        card_number = request_data.get('CardNumber', None)
        cvv = request_data.get('CVV', None)
        expiry = request_data.get('Expiry', None)
        payer_name = request_data.get('CardHolderName', None)
        address = request_data.get('CardHolderAddress', None)
        payee_account_number = request_data.get('PayeeBankAccNum', None)
        payee_sort_code = request_data.get('PayeeBankSortCode', None)
        amount = request_data.get('Amount', None)
        payee_currency_code = request_data.get('PayeeCurrencyCode', None)
        """
        pns_request_data.update({
            'CardNumber': card_number,
            'Expiry': expiry,
            'CVV': cvv,
            'HolderName': payer_name,
            'BillingAddress': address,
            'Amount': amount,
            'CurrencyCode': payee_currency_code,
            'AccountNumber': payee_account_number,
            'Sort-Code': payee_sort_code
        })
        """

        # response = request.post(pns_url, data=pns_request_data)
        response = temp
        pns_status = response.get('StatusCode', None)
        pns_comment = response.get('Comment', None)
        # response.status_code -- use this
        if pns_status != 200:
            return error_response(response_data, 301)
        else:
            response_data['Comment'] = pns_comment
            return JsonResponse(response_data, status=pns_status)
    else:
        return error_response(response_data, 105)


def request_refund_pns(request):
    # The JSON default data of the response, stored in a dictionary
    response_data = {
        'ErrorCode': None,
        'Comment': ""
    }
    pns_status = 400  # Default to a bad request

    pns_url = ""

    if request.method == 'POST':

        response = request.post(pns_url, data=request)

        pns_status = response.get('StatusCode', None)
        pns_comment = response.get('Comment', None)

        if pns_status != 200:
            return error_response(response_data, 301)
        else:
            response_data['Comment'] = pns_comment

    else:
        return error_response(response_data, 105)

    return JsonResponse(response_data, status=pns_status)


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

        # Check if all values required are present
        if all(value is not None for value in [currency_code_from, currency_code_to, amount, date]):
            try:
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

            # Gives the appropriate error code if a currency code provided does not exist
            # in the database
            except Currency.DoesNotExist:
                return error_response(response_data, 104, "Error. One or more currencies provided does not exist")

        # Runs if a parameter is not present
        else:
            # Updates the response with the error that a parameter is missing
            return error_response(response_data, 102)

    else:
        return error_response(response_data, 105)


codes = {
    100: 'Request body empty.',
    101: 'Request body in incorrect format',
    102: 'Could not find field "{}".',
    103: 'Field {0} is a {1}, when {2} was expected.',
    104: 'Invalid Field(s): {0}',
    201: 'An error occurred with currency conversion.',
    301: 'An error occurred with contacting the Payment Network Service.',
}
