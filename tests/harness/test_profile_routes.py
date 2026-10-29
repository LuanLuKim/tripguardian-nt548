"""The account's profile entries over HTTP (docs/TRIP_UNDERSTANDING.md §17): see, edit, pause, delete; consent."""

import threading
from http.server import ThreadingHTTPServer

import http.client
import pytest

from test_harness_server import USERS, FakeAccounts, call, make

EID = "0123456789ab"


class FakeTrip:
    def __init__(self):
        self.entries = {USERS["tok-a"]: {EID: {"id": EID, "statement": "Thích đi chậm", "paused": False}}}
        self.paused = False

    def profile(self, uid):
        return {"enabled": True, "paused": self.paused, "entries": list(self.entries.get(uid, {}).values())}

    def edit_entry(self, uid, eid, patch):
        if set(patch) - {"statement", "paused"}:
            raise ValueError("an entry takes statement and / or paused")
        entry = self.entries.get(uid, {})[eid]  # KeyError -> 404
        entry.update(patch)
        return entry

    def delete_entry(self, uid, eid):
        return self.entries.get(uid, {}).pop(eid, None) is not None

    def pause_profile(self, uid, paused):
        self.paused = paused
        return self.profile(uid)


class RememberAccounts(FakeAccounts):
    def remember(self, uid, on):
        self.remembered = (uid, on)
        return {"id": uid, "consents": {"patterns": on}}


@pytest.fixture
def parts():
    harness, tools = make()
    tools["trip"].__class__ = type("TripWithProfile", (type(tools["trip"]), FakeTrip), {})
    FakeTrip.__init__(tools["trip"])
    return harness, tools["trip"], RememberAccounts()


@pytest.fixture
def client(parts):
    from harness.server import handler
    harness, _, accounts = parts
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler(harness, accounts, "http://app.test"))
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    connection = http.client.HTTPConnection("127.0.0.1", server.server_address[1], timeout=5)
    yield connection
    connection.close()
    server.shutdown()
    server.server_close()
    worker.join()


def test_user_sees_edits_and_deletes_own_entries(client, parts):
    code, body = call(client, "GET", "/api/harness/me/profile")
    assert code == 200 and [e["id"] for e in body["entries"]] == [EID]
    assert call(client, "GET", "/api/harness/me/profile", token="tok-b")[1]["entries"] == []  # another account's: none
    code, entry = call(client, "PATCH", f"/api/harness/me/profile/entries/{EID}", {"statement": "Đi thong thả"})
    assert code == 200 and entry["statement"] == "Đi thong thả"
    assert call(client, "PATCH", f"/api/harness/me/profile/entries/{EID}", {"color": 1})[0] == 400
    assert call(client, "PATCH", f"/api/harness/me/profile/entries/{EID}", {"paused": True}, token="tok-b")[0] == 404
    assert call(client, "DELETE", f"/api/harness/me/profile/entries/{EID}", token="tok-b")[0] == 404
    assert call(client, "DELETE", f"/api/harness/me/profile/entries/{EID}") == (200, {"deleted": True})
    assert call(client, "DELETE", f"/api/harness/me/profile/entries/{EID}")[0] == 404
    assert call(client, "GET", "/api/harness/me/profile")[1]["entries"] == []


def test_pause_the_whole_profile(client):
    assert call(client, "PATCH", "/api/harness/me/profile", {"paused": True})[1]["paused"] is True
    assert call(client, "PATCH", "/api/harness/me/profile", {"paused": "yes"})[0] == 400


def test_remember_consent_is_written_for_members_only(client, parts):
    code, me = call(client, "POST", "/api/harness/me/remember", {"on": True})
    assert code == 200 and me["consents"]["patterns"] is True and parts[2].remembered == (USERS["tok-a"], True)
    assert call(client, "POST", "/api/harness/me/remember", {"on": 1})[0] == 400


def test_guests_have_no_profile(client):
    for method, path, data in (("GET", "/api/harness/me/profile", None),
                               ("PATCH", "/api/harness/me/profile", {"paused": True}),
                               ("PATCH", f"/api/harness/me/profile/entries/{EID}", {"paused": True}),
                               ("DELETE", f"/api/harness/me/profile/entries/{EID}", None),
                               ("POST", "/api/harness/me/remember", {"on": True})):
        assert call(client, method, path, data, token="tok-g")[0] == 403
