from django.urls import reverse
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.games.models import Game
from apps.teams.models import (
    INVITE_ROLES,
    RosterAccountStatus,
    Team,
    TeamInvite,
    TeamMembership,
    TeamRole,
)
from apps.teams.selectors import get_account_status, roster_account_issues


class TeamMemberSerializer(serializers.ModelSerializer[TeamMembership]):
    nickname = serializers.CharField(source="user.profile.nickname", read_only=True)
    game_account_status = serializers.SerializerMethodField(
        help_text="Game account for the team's discipline; required to enter tournaments."
    )

    class Meta:
        model = TeamMembership
        fields = ("id", "nickname", "role", "joined_at", "game_account_status")
        read_only_fields = fields

    @extend_schema_field(serializers.ChoiceField(choices=RosterAccountStatus.choices))
    def get_game_account_status(self, membership: TeamMembership) -> str:
        # Rosters from selectors come annotated; single memberships are looked up.
        status = getattr(membership, "account_status", None)
        return status or get_account_status(membership.user, membership.game)


class TeamSerializer(serializers.ModelSerializer[Team]):
    game: serializers.SlugRelatedField[Game] = serializers.SlugRelatedField(
        slug_field="slug", queryset=Game.objects.filter(is_active=True)
    )
    captain = serializers.CharField(source="captain.profile.nickname", read_only=True)

    class Meta:
        model = Team
        fields: tuple[str, ...] = (
            "id",
            "name",
            "tag",
            "logo",
            "game",
            "captain",
            "created_at",
            "disbanded_at",
        )
        read_only_fields: tuple[str, ...] = ("id", "captain", "created_at", "disbanded_at")
        extra_kwargs = {"logo": {"required": False}}
        # Uniqueness is checked by the service, which reports the right field.
        validators: list[object] = []


class TeamDetailSerializer(TeamSerializer):
    roster = TeamMemberSerializer(many=True, read_only=True)
    all_accounts_linked = serializers.SerializerMethodField(
        help_text="Every member has a game account for the discipline (verified or not)."
    )

    class Meta(TeamSerializer.Meta):
        fields = (*TeamSerializer.Meta.fields, "roster", "all_accounts_linked")
        read_only_fields = fields

    @extend_schema_field(OpenApiTypes.BOOL)
    def get_all_accounts_linked(self, team: Team) -> bool:
        return roster_account_issues(team.roster).all_linked  # type: ignore[attr-defined]


class TeamInviteCreateSerializer(serializers.Serializer[TeamInvite]):
    nickname = serializers.CharField(
        required=False, allow_blank=True, help_text="Empty for a shareable link invite."
    )
    role = serializers.ChoiceField(
        choices=[TeamRole.PLAYER, TeamRole.SUBSTITUTE], default=TeamRole.PLAYER
    )


class TeamInviteSerializer(serializers.ModelSerializer[TeamInvite]):
    team = TeamSerializer(read_only=True)
    invitee = serializers.CharField(
        source="invitee.profile.nickname", read_only=True, allow_null=True, default=None
    )
    url = serializers.SerializerMethodField()

    class Meta:
        model = TeamInvite
        fields = ("id", "team", "invitee", "role", "status", "expires_at", "token", "url")
        read_only_fields = fields

    def get_url(self, invite: TeamInvite) -> str:
        path = reverse("teams:invite", args=[invite.token])
        request = self.context.get("request")
        return request.build_absolute_uri(path) if request else path


class MemberRoleSerializer(serializers.Serializer[TeamMembership]):
    role = serializers.ChoiceField(choices=INVITE_ROLES)


class CaptainTransferSerializer(serializers.Serializer[Team]):
    membership_id = serializers.IntegerField(help_text="Roster entry id of the new captain.")
