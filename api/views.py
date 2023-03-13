import datetime

from django.http import HttpResponse, Http404


def initiate_payment(request):
    return HttpResponse("hello world")


def initiate_refund(request):
    return HttpResponse("hello world")


def initiate_cancellation(request):
    return HttpResponse("hello world")


def request_transaction_pns(request):
    return HttpResponse("hello world")


def request_refund_pns(request):
    return HttpResponse("hello world")


def convert_currency(request):
    return HttpResponse("hello world")


def current_datetime(request):
    now = datetime.datetime.now()
    html = "<html><body>It is now %s.</body></html>" % now
    return HttpResponse(html)


def hours_ahead(request, offset):
    try:
        offset = int(offset)
    except ValueError:
        raise Http404()
    dt = datetime.datetime.now() + datetime.timedelta(hours=offset)
    html = "<html><body>In %s hour(s), it will be %s.</body></html>" % (offset, dt)
    return HttpResponse(html)


def hello(request):
    return HttpResponse("Hello world")
