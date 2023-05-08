import json
from datetime import date

from django.http import HttpResponse, JsonResponse

from models import Transaction


def initiate_payment(request):
    status = 400  # defaults to a bad request to avoid repeating multiple lines of code setting it to 400
    error_code = None
    comment = ""

    pns_url = ""

    if request.method == 'POST':
        request_data = json.loads(request.body)  # Parses the JSON response
        card_number = request_data.get('CardNumber', None)
        cvv = request_data.get('CVV', None)
        expiry = request_data.get('Expiry', None)
        name = request_data.get('CardHolderName', None)
        address = request_data.get('CardHolderAddress', None)
        email = request_data.get('Email', None)
        amount = request_data.get('Amount', None)
        currency_code = request_data.get('CurrencyCode', None)

        if all(value is not None for value in [card_number, cvv, expiry, name,
                                               address, email, amount, currency_code]):

            data = {'key1': 'value1', 'key2': 'value2'}
        json_data = json.dumps(data)
        response = request.post(pns_url, data=json_data)

        # send info to pns, return it back
    return HttpResponse("hello world")


def initiate_refund(request):
    status = 400  # defaults to a bad request to avoid repeating multiple lines of code setting it to 400
    error_code = None
    comment = ""

    if request.method == 'POST':
        request_data = json.loads(request.body)  # Parses the JSON response

        # check these for validity, maybe store them in the db

        # check if no vals are none

        transaction_id = request_data.get('TransactionUUID', None)
        amount = request_data.get('Amount', None)
        currency_code = request_data.get('CurrencyCode', None)

        if all(value is not None for value in [transaction_id, amount, currency_code]):
            try:
                # transaction will already exist from initial payment
                curr_transaction = Transaction.objects.get(id=transaction_id)

            except Transaction.DoesNotExist:
                error_code = 1
                comment = "Error. Transaction does not exist"
                # return error saying transaction does not exist

            response = request_refund_pns(request)

            status = response.get('StatusCode', None)
            comment = response.get('Comment', None)

            if status != 200:
                #get error code and comment
                error_code = 1
            else:
                curr_transaction.transactionStatus = "Refunded"

        else:
            error_code = 1
            comment = "Error. One or more parameters have not been supplied"

    final_response = {'Status': status, 'ErrorCode': error_code, 'Comment': comment}
    json_response = json.dumps(final_response)

    return JsonResponse(json_response)


def initiate_cancellation(request):
    status = 400  # defaults to a bad request to avoid repeating multiple lines of code setting it to 400
    error_code = None
    comment = ""

    if request.method == 'POST':
        request_data = json.loads(request.body)  # Parses the JSON response
        transaction_id = request_data.get('TransactionUUID', None)

        if transaction_id is not None:
            try:
                cancel_transaction = Transaction.objects.get(id=transaction_id)
                cancel_transaction.transactionStatus = "Cancelled"
                cancel_transaction.save()

                status = 200
                comment = "Cancellation Successful"

            except Transaction.DoesNotExist:
                error_code = 2
                comment = "Error. Transaction does not exist"
                # return error saying transaction does not exist
        else:
            error_code = 1
            comment = "Error. No transaction parameter was provided"
            # return error response that transaction id is invalid

    response_data = {'Status': status, 'ErrorCode': error_code, 'Comment': comment}
    json_response = json.dumps(response_data)

    return JsonResponse(json_response)


def request_transaction_pns(request):
    return HttpResponse("hello world")


def request_refund_pns(request):
    status = 400  # defaults to a bad request to avoid repeating multiple lines of code setting it to 400
    error_code = None
    comment = ""

    pns_url = ""

    if request.method == 'POST':
        request_data = json.loads(request.body)  # Parses the JSON response

        transaction_id = request_data.get('TransactionUUID', None)
        amount = request_data.get('Amount', None)
        currency_code = request_data.get('CurrencyCode', None)

        if all(value is not None for value in [transaction_id, amount, currency_code]):
            response = request.post(pns_url, data=request)
            return JsonResponse(response)

        error_code = 1
        comment = "Error. One or more arguments missing from parameters supplied."

    error_response = {'Status': status, 'ErrorCode': error_code, 'Comment': comment}
    json_error_response = json.dumps(error_response)

    return JsonResponse(json_error_response)


def convert_currency(request):
    currency_url = 'endpoint'

    if request.method == 'POST':
        request_data = json.loads(request.body)  # Parses the JSON response
        currency_code = request_data.get('CurrencyCode', None)
        amount = request_data.get('Amount', None)

        if currency_code is not None and amount is not None:
            # get from db
            # no results? throw error
            currency_from = ""  # from db
            currency_to = ""  # from db
            curr_date = str(date.today())  # in y-m-d, may need to change
            payload = {'CurrencyFrom': currency_from, 'CurrencyTo': currency_to,
                       'Date': curr_date, 'Amount': amount}

            payload_json = json.dumps(payload)

            response = request.post(currency_url, data=payload_json)

            # return response

        else:
            if amount is None:
                print("error")
                # error code that amount is invalid
            else:
                print("error")
                # error code that currency code is invalid

    # return JsonResponse(result)
    return HttpResponse("hello world")
