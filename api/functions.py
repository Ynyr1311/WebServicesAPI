import json


def check_valid_request(request, response_data):
    if len(request.body) == 0:
        # Returns error code 100 if it is
        response_data.update({
            'ErrorCode': 100,
            'Comment': "Error. Body of the request is empty"
        })
        return response_data

    # Checks if the request can be converted into JSON successfully
    try:
        request_data = json.loads(request.body)
        return request_data

    except json.JSONDecodeError:
        # If it can't, then return error 101
        response_data.update({
            'ErrorCode': 101,
            'Comment': "Error. Request is not in JSON format"
        })
        return response_data
