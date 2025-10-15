# Role-based Access functions for user_passes_test in:
# 'from django.contrib.auth.decorators import user_passes_test'

# check for admin role
def is_admin(user):
    # Check if the user is an admin

    for role in user.roles.all():
        if role.name == "Admin":
            return True

# check for HR role
def is_hr(user):
    # Check if the user is an HR

    for role in user.roles.all():
        if role.name == "HR":
            return True