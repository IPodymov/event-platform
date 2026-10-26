import factory
from factory.django import DjangoModelFactory, Password

from apps.accounts.models import User

DEFAULT_PASSWORD = "correct-horse-battery"


class UserFactory(DjangoModelFactory[User]):
    class Meta:
        model = User
        django_get_or_create = ("email",)
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"player{n}@example.com")
    password = Password(DEFAULT_PASSWORD)
