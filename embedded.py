"""
Embedded Python SDK — authenticate and fetch your voice memo data.

This is the shared client used by all connectors. You can also use it
directly in your own scripts:

    from embedded import EmbeddedClient

    client = EmbeddedClient()
    client.login("you@example.com", "your-password")
    memos = client.get_memos()

    for memo in memos:
        print(memo["category"], memo["summary"][:80])
"""

import sys
from collections import defaultdict
from datetime import datetime, timezone

import requests

# ---------------------------------------------------------------------------
# Public service endpoints (safe to embed — auth is per-user)
# ---------------------------------------------------------------------------

FIREBASE_API_KEY = "AIzaSyCG9LT3wouXq9mWos2h0pc-3S7IH1IfgVI"
GRAY_MATTER_API = "https://us-central1-embedded-760a8.cloudfunctions.net"

FIREBASE_AUTH_URL = (
    "https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword"
    f"?key={FIREBASE_API_KEY}"
)


class AuthError(Exception):
    """Raised when authentication fails."""


class APIError(Exception):
    """Raised when the Embedded API returns an error."""


class EmbeddedClient:
    """Client for the Embedded voice memo API.

    Authenticates with your Embedded account (Firebase) and fetches
    your data through a secure API that enforces per-user isolation.
    """

    def __init__(self):
        self._id_token: str | None = None
        self._uid: str | None = None
        self._email: str | None = None

    @property
    def is_authenticated(self) -> bool:
        return self._id_token is not None

    @property
    def uid(self) -> str | None:
        return self._uid

    @property
    def email(self) -> str | None:
        return self._email

    def login(self, email: str, password: str) -> None:
        """Authenticate with your Embedded account.

        Args:
            email: Your Embedded account email.
            password: Your Embedded account password.

        Raises:
            AuthError: If authentication fails.
        """
        resp = requests.post(
            FIREBASE_AUTH_URL,
            json={"email": email, "password": password, "returnSecureToken": True},
            timeout=15,
        )
        if resp.status_code != 200:
            msg = resp.json().get("error", {}).get("message", resp.text)
            raise AuthError(f"Authentication failed: {msg}")

        data = resp.json()
        self._id_token = data["idToken"]
        self._uid = data["localId"]
        self._email = email

    def get_memos(
        self,
        since: str | None = None,
        category: str | None = None,
        include_embeddings: bool = False,
    ) -> list[dict]:
        """Fetch your voice memos.

        Returns a list of memo dicts, each with stitched transcriptions
        from all chunks. Multi-chunk memos are automatically combined.

        Args:
            since: ISO timestamp — only return memos created after this time.
            category: Filter by category (e.g., "Meeting", "Idea", "ToDo").
            include_embeddings: If True, include the 3072-dim embedding vectors.

        Returns:
            List of memo dicts with keys: memo_id, transcription, summary,
            category, audio_file_name, created_at, tags, chunk_count.
            If include_embeddings is True, also includes raw chunk data.

        Raises:
            AuthError: If not logged in or token expired.
            APIError: If the API returns an error.
        """
        if not self._id_token:
            raise AuthError("Not authenticated. Call login() first.")

        payload: dict = {"id_token": self._id_token}
        if since:
            payload["since"] = since
        if category:
            payload["category"] = category
        if include_embeddings:
            payload["include_embeddings"] = True

        resp = requests.post(
            f"{GRAY_MATTER_API}/get-user-data",
            json=payload,
            timeout=120,
        )

        if resp.status_code == 401:
            raise AuthError(f"Session expired or invalid: {resp.json().get('error')}")
        if resp.status_code != 200:
            raise APIError(f"API error ({resp.status_code}): {resp.text[:300]}")

        rows = resp.json().get("rows", [])
        if not rows:
            return []

        return self._stitch_memos(rows, include_embeddings)

    def get_raw_chunks(
        self,
        since: str | None = None,
        category: str | None = None,
        include_embeddings: bool = False,
    ) -> list[dict]:
        """Fetch raw embedding chunks without stitching.

        Useful for building search indexes or custom processing pipelines.
        Each row represents one chunk of a memo.

        Returns:
            List of raw chunk dicts directly from the API.
        """
        if not self._id_token:
            raise AuthError("Not authenticated. Call login() first.")

        payload: dict = {"id_token": self._id_token}
        if since:
            payload["since"] = since
        if category:
            payload["category"] = category
        if include_embeddings:
            payload["include_embeddings"] = True

        resp = requests.post(
            f"{GRAY_MATTER_API}/get-user-data",
            json=payload,
            timeout=120,
        )

        if resp.status_code == 401:
            raise AuthError(f"Session expired or invalid: {resp.json().get('error')}")
        if resp.status_code != 200:
            raise APIError(f"API error ({resp.status_code}): {resp.text[:300]}")

        return resp.json().get("rows", [])

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _stitch_memos(rows: list[dict], include_embeddings: bool = False) -> list[dict]:
        """Group chunks by memo_id and combine into single memo dicts."""
        grouped: dict[str, list[dict]] = defaultdict(list)
        for row in rows:
            grouped[row["memo_id"]].append(row)

        memos = []
        for memo_id, chunks in grouped.items():
            chunks.sort(key=lambda c: c.get("chunk_index", 0))
            first = chunks[0]

            # Stitch transcription from all chunks
            transcription_parts = []
            for chunk in chunks:
                text = chunk.get("transcription") or chunk.get("text_preview") or ""
                if text and text not in transcription_parts:
                    transcription_parts.append(text)

            memo = {
                "memo_id": memo_id,
                "transcription": "\n\n".join(transcription_parts),
                "summary": first.get("summary") or "",
                "category": first.get("category") or "Other",
                "audio_file_name": first.get("audio_file_name") or "",
                "created_at": first.get("created_at") or "",
                "updated_at": first.get("updated_at") or "",
                "tags": first.get("tags") or "",
                "chunk_count": len(chunks),
            }

            if include_embeddings:
                memo["chunks"] = chunks

            memos.append(memo)

        return memos
