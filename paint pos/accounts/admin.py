from django.contrib import admin

from .models import Profile


@admin.register(Profile)
class ProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "branch", "role")
    list_filter = ("role", "branch")
    search_fields = ("user__username", "user__first_name", "user__last_name")
