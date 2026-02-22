from django.db import migrations


REGULAR_USERS_GROUP = "regular_users"
BUSINESS_USERS_GROUP = "business_users"


def seed_groups_and_discounts(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    GroupDiscount = apps.get_model("accounts", "GroupDiscount")

    regular_group, _ = Group.objects.get_or_create(name=REGULAR_USERS_GROUP)
    business_group, _ = Group.objects.get_or_create(name=BUSINESS_USERS_GROUP)

    GroupDiscount.objects.get_or_create(group=regular_group, defaults={"percentage": 0, "is_active": True})
    GroupDiscount.objects.get_or_create(group=business_group, defaults={"percentage": 10, "is_active": True})


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_groupdiscount"),
        ("auth", "0012_alter_user_first_name_max_length"),
    ]

    operations = [
        migrations.RunPython(seed_groups_and_discounts, noop_reverse),
    ]
