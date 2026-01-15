"""API integration tests for authentication endpoints."""
import pytest
from httpx import AsyncClient


class TestProfileEndpoints:
    """Tests for profile management endpoints."""

    @pytest.mark.asyncio
    async def test_list_profiles_empty(self, client: AsyncClient):
        """GET /api/auth/profiles should return empty list initially."""
        response = await client.get("/api/auth/profiles")
        assert response.status_code == 200
        assert response.json() == []

    @pytest.mark.asyncio
    async def test_create_profile_success(self, client: AsyncClient, sample_profile_data: dict):
        """POST /api/auth/profiles should create a new profile."""
        response = await client.post("/api/auth/profiles", json=sample_profile_data)
        assert response.status_code == 200

        data = response.json()
        assert data["name"] == sample_profile_data["name"]
        assert data["avatar"] == sample_profile_data["avatar"]
        assert "id" in data
        assert "created_at" in data
        assert "pin_hash" not in data  # Should not expose hash

    @pytest.mark.asyncio
    async def test_create_profile_first_is_admin(self, client: AsyncClient, sample_profile_data: dict):
        """First created profile should be admin."""
        response = await client.post("/api/auth/profiles", json=sample_profile_data)
        assert response.status_code == 200
        assert response.json()["is_admin"] is True

    @pytest.mark.asyncio
    async def test_create_profile_second_not_admin(self, client: AsyncClient, sample_profile_data: dict):
        """Second profile should not be admin."""
        # Create first profile (admin)
        await client.post("/api/auth/profiles", json=sample_profile_data)

        # Create second profile
        second_profile = {**sample_profile_data, "name": "SecondUser", "pin": "5678"}
        response = await client.post("/api/auth/profiles", json=second_profile)
        assert response.status_code == 200
        assert response.json()["is_admin"] is False

    @pytest.mark.asyncio
    async def test_create_profile_missing_name(self, client: AsyncClient):
        """Creating profile without name should fail validation."""
        response = await client.post("/api/auth/profiles", json={"pin": "1234"})
        assert response.status_code == 422  # Validation error

    @pytest.mark.asyncio
    async def test_create_profile_missing_pin(self, client: AsyncClient):
        """Creating profile without PIN should fail validation."""
        response = await client.post("/api/auth/profiles", json={"name": "Test"})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_create_profile_short_pin(self, client: AsyncClient):
        """PIN shorter than 4 characters should fail validation."""
        response = await client.post("/api/auth/profiles", json={"name": "Test", "pin": "123"})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_list_profiles_after_creation(self, client: AsyncClient, sample_profile_data: dict):
        """GET /api/auth/profiles should return created profiles."""
        # Create a profile
        await client.post("/api/auth/profiles", json=sample_profile_data)

        # List profiles
        response = await client.get("/api/auth/profiles")
        assert response.status_code == 200
        profiles = response.json()
        assert len(profiles) == 1
        assert profiles[0]["name"] == sample_profile_data["name"]


class TestLoginEndpoint:
    """Tests for login endpoint."""

    @pytest.mark.asyncio
    async def test_login_success(self, client: AsyncClient, sample_profile_data: dict):
        """POST /api/auth/login with correct PIN should return token."""
        # Create profile
        create_response = await client.post("/api/auth/profiles", json=sample_profile_data)
        profile_id = create_response.json()["id"]

        # Login
        login_response = await client.post("/api/auth/login", json={
            "profile_id": profile_id,
            "pin": sample_profile_data["pin"]
        })
        assert login_response.status_code == 200

        data = login_response.json()
        assert "access_token" in data
        assert "profile" in data
        assert data["profile"]["id"] == profile_id

    @pytest.mark.asyncio
    async def test_login_wrong_pin(self, client: AsyncClient, sample_profile_data: dict):
        """Login with wrong PIN should return 401."""
        # Create profile
        create_response = await client.post("/api/auth/profiles", json=sample_profile_data)
        profile_id = create_response.json()["id"]

        # Login with wrong PIN
        login_response = await client.post("/api/auth/login", json={
            "profile_id": profile_id,
            "pin": "9999"
        })
        assert login_response.status_code == 401
        assert "Incorrect PIN" in login_response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_nonexistent_profile(self, client: AsyncClient):
        """Login with non-existent profile should return 404."""
        login_response = await client.post("/api/auth/login", json={
            "profile_id": "nonexistent-id",
            "pin": "1234"
        })
        assert login_response.status_code == 404
        assert "Profile not found" in login_response.json()["detail"]

    @pytest.mark.asyncio
    async def test_login_missing_profile_id(self, client: AsyncClient):
        """Login without profile_id should fail validation."""
        response = await client.post("/api/auth/login", json={"pin": "1234"})
        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_login_missing_pin(self, client: AsyncClient, sample_profile_data: dict):
        """Login without PIN should fail validation."""
        create_response = await client.post("/api/auth/profiles", json=sample_profile_data)
        profile_id = create_response.json()["id"]

        response = await client.post("/api/auth/login", json={"profile_id": profile_id})
        assert response.status_code == 422


class TestDeleteProfileEndpoint:
    """Tests for profile deletion endpoint."""

    @pytest.mark.asyncio
    async def test_delete_profile_success(self, client: AsyncClient, sample_profile_data: dict):
        """DELETE /api/auth/profiles/{id} should delete profile."""
        # Create profile
        create_response = await client.post("/api/auth/profiles", json=sample_profile_data)
        profile_id = create_response.json()["id"]

        # Delete profile
        delete_response = await client.delete(f"/api/auth/profiles/{profile_id}")
        assert delete_response.status_code == 200
        assert delete_response.json()["status"] == "deleted"

        # Verify deletion
        list_response = await client.get("/api/auth/profiles")
        assert len(list_response.json()) == 0

    @pytest.mark.asyncio
    async def test_delete_nonexistent_profile(self, client: AsyncClient):
        """Deleting non-existent profile should return 404."""
        response = await client.delete("/api/auth/profiles/nonexistent-id")
        assert response.status_code == 404


class TestLegacyHashUpgrade:
    """Tests for legacy hash upgrade on login."""

    @pytest.mark.asyncio
    async def test_legacy_hash_upgraded_on_login(self, client: AsyncClient, test_db):
        """Login with legacy hash should upgrade to bcrypt."""
        from app.api.routes.auth import _legacy_hash_pin
        from app.models.database import Profile
        from sqlalchemy import select
        import uuid

        # Directly insert profile with legacy hash
        legacy_hash = _legacy_hash_pin("5678")
        profile_id = uuid.uuid4().hex
        profile = Profile(
            id=profile_id,
            name="LegacyUser",
            pin_hash=legacy_hash,
            avatar="default",
            is_admin=True,
        )
        test_db.add(profile)
        await test_db.commit()

        # Verify it's a legacy hash
        assert not legacy_hash.startswith("$2b$")

        # Login (should upgrade hash)
        login_response = await client.post("/api/auth/login", json={
            "profile_id": profile_id,
            "pin": "5678"
        })
        assert login_response.status_code == 200

        # Verify hash was upgraded
        await test_db.refresh(profile)
        result = await test_db.execute(select(Profile).where(Profile.id == profile_id))
        updated_profile = result.scalar_one()
        assert updated_profile.pin_hash.startswith("$2b$")
