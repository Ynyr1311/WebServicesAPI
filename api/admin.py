from django.contrib import admin

from api.models import PersonalAccount, BusinessAccount, Transaction, PaymentDetails, BankDetails

# Register your models here.

admin.site.register(PersonalAccount)
admin.site.register(BusinessAccount)
admin.site.register(Transaction)
admin.site.register(PaymentDetails)
admin.site.register(BankDetails)
