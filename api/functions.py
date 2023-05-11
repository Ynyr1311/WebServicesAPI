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
    201: 'An error occurred with currency conversion. ',
    301: 'An error occurred with contacting the Payment Network Service. ',
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


# Function for creating correct error codes and messages to be sent to the aggregator
def error_response(response_data, error_code, error_message=None):
    response_data['ErrorCode'] = error_code

    # The generic messages for each error code
    if error_message is None:
        response_data['Comment'] = generic_error_messages.get(error_code)

    else:
        # Keeps the comment provided
        response_data['Comment'] = error_message

    return JsonResponse(response_data, status=400)


# Returns the error code and comments for any errors coming from another API that's being interacted with.
def error_response_external(api_response, response_data, error_code):
    # Get the body of response from the external api
    response_body = json.loads(api_response.text)

    # Set the error code to the one provided
    response_data['ErrorCode'] = error_code
    # Append the generic error message to the start. The following string has the more detailed error message
    # from the external API.
    response_data['Comment'] = generic_error_messages.get(error_code) + response_body['Comment']
    return JsonResponse(response_data, status=400)
