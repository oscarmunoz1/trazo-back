from django.contrib import admin
from .models import CarbonSource, CarbonOffsetAction, CarbonEntry, CarbonCertification, CarbonBenchmark, CarbonReport, CarbonAuditLog

# Register your models here.
admin.site.register(CarbonSource)
admin.site.register(CarbonOffsetAction)
admin.site.register(CarbonEntry)
admin.site.register(CarbonCertification)
admin.site.register(CarbonBenchmark)
admin.site.register(CarbonReport)
admin.site.register(CarbonAuditLog)
