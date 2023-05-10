import json

from django.http import JsonResponse

# Stores the generic error messages for each error code
generic_error_messages = {
    100: "Error. Body of the request is empty",
    101: "Error. Request is not in JSON format",
    102: "Error. One or more parameters were not provided",
    103: "Error. One or more parameters were not of a valid type",
    104: "Error. One or more fields are invalid",
    105: "Error. This function only accepts POST requests",
    106: 'Payer card details could not be found',
    107: 'Payee bank account details could not be found',
    108: 'Payer personal account could not be found',
    109: 'Payee business account details could not be found',
    201: 'An error occurred with currency conversion.',
    301: 'An error occurred with contacting the Payment Network Service.',
    401: 'Could not access database.',
    402: 'Transaction with the parameters provided could not be located.',
    403: 'Refund could not be completed.',
    404: 'Original transaction already refunded or cancelled.'
}


def check_valid_request(request, response_data):
    if len(request.body) == 0:
        # Returns error code 100 if it is
        return error_response(response_data, 100)

    # Checks if the request can be converted into JSON successfully
    try:
        request_data = json.loads(request.body)
        return request_data

    except json.JSONDecodeError:
        # If it can't, then return error 101
        return error_response(response_data, 101)


def error_response(response_data, error_code, error_message=None):
    response_data['ErrorCode'] = error_code

    # The generic messages for each error code
    if error_message is None:
        response_data['Comment'] = generic_error_messages.get(error_code)

    else:
        response_data['Comment'] = error_message

    return JsonResponse(response_data, status=400)


def sucessful_response(response_data, message):
    pass
