import factory
from factory.django import DjangoModelFactory, Password

from apps.accounts.models import Profile, User

DEFAULT_PASSWORD = "correct-horse-battery"


class ProfileFactory(DjangoModelFactory[Profile]):
    class Meta:
        model = Profile

    user = factory.SubFactory("apps.accounts.tests.factories.UserFactory", profile=None)
    nickname = factory.Sequence(lambda n: f"player{n}")


class UserFactory(DjangoModelFactory[User]):
    class Meta:
        model = User
        django_get_or_create = ("email",)
        skip_postgeneration_save = True

    email = factory.Sequence(lambda n: f"player{n}@example.com")
    password = Password(DEFAULT_PASSWORD)
    profile = factory.RelatedFactory(ProfileFactory, factory_related_name="user")
