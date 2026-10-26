from django.db import migrations

ALL_SERIES = [1, 3, 5]

DISCIPLINES = [
    {
        "slug": "cs2",
        "name": "Counter-Strike 2",
        "participant_type": "team",
        "roster_size": 5,
        "max_substitutes": 2,
        "allowed_series": ALL_SERIES,
        "result_verification": "manual",
    },
    {
        "slug": "dota2",
        "name": "Dota 2",
        "participant_type": "team",
        "roster_size": 5,
        "max_substitutes": 2,
        "allowed_series": ALL_SERIES,
        "result_verification": "opendota",
    },
    {
        "slug": "wildrift",
        "name": "League of Legends: Wild Rift",
        "participant_type": "team",
        "roster_size": 5,
        "max_substitutes": 2,
        "allowed_series": ALL_SERIES,
        "result_verification": "manual",
    },
    {
        "slug": "hearthstone",
        "name": "Hearthstone",
        "participant_type": "solo",
        "roster_size": 1,
        "max_substitutes": 0,
        "allowed_series": ALL_SERIES,
        "result_verification": "manual",
    },
]


def seed(apps, schema_editor):
    Game = apps.get_model("games", "Game")
    for discipline in DISCIPLINES:
        defaults = {k: v for k, v in discipline.items() if k != "slug"}
        Game.objects.update_or_create(slug=discipline["slug"], defaults=defaults)


class Migration(migrations.Migration):
    dependencies = [
        ("games", "0001_initial"),
    ]

    # Reversal keeps the rows: tournaments and accounts will reference them.
    operations = [migrations.RunPython(seed, migrations.RunPython.noop)]
