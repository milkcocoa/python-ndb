import itertools
import time

import pytest

from google.cloud import datastore
from google.cloud import ndb

from . import KIND, OTHER_NAMESPACE


def all_entities(client):
    return itertools.chain(
        client.query(kind=KIND).fetch(),
        client.query(namespace=OTHER_NAMESPACE).fetch(),
    )


@pytest.fixture(scope="module", autouse=True)
def initial_clean():
    # Make sure database is in clean state at beginning of test run
    client = datastore.Client()
    for entity in all_entities(client):
        client.delete(entity.key)


@pytest.fixture(scope="session")
def deleted_keys():
    return set()


@pytest.fixture
def to_delete():
    return []


@pytest.fixture
def ds_client(to_delete, deleted_keys):
    client = datastore.Client()

    # Make sure we're leaving database as clean as we found it after each test
    results = [
        entity
        for entity in all_entities(client)
        if entity.key not in deleted_keys
    ]
    assert not results

    yield client

    if to_delete:
        client.delete_multi(to_delete)
        deleted_keys.update(to_delete)

    # Datastore takes some time to delete entities even after it says it's
    # deleted them. (With Firestore using the Datastore interface, an entity is
    # deleted when you get a return from a call to delete.) Keep checking for
    # up to 2 minutes.
    deadline = time.time() + 120
    while True:
        results = list(all_entities(client))
        print(results)
        if not results:
            # all clean, yeah
            break

        # Make sure we're only waiting on entities that have been deleted
        not_deleted = [
            entity for entity in results if entity.key not in deleted_keys
        ]
        assert not not_deleted

        # How are we doing on time?
        assert (
            time.time() < deadline
        ), "Entities taking too long to delete: {}".format(results)

        # Give Datastore a second to find a consistent state before checking
        # again
        time.sleep(1)


@pytest.fixture
def ds_entity(ds_client, dispose_of):
    def make_entity(*key_args, **entity_kwargs):
        key = ds_client.key(*key_args)
        assert ds_client.get(key) is None
        entity = datastore.Entity(key=key)
        entity.update(entity_kwargs)
        ds_client.put(entity)
        dispose_of(key)

        return entity

    yield make_entity


@pytest.fixture
def dispose_of(ds_client, to_delete):
    def delete_entity(ds_key):
        to_delete.append(ds_key)

    return delete_entity


@pytest.fixture
def namespace():
    return ""


@pytest.fixture
def client_context(namespace):
    client = ndb.Client(namespace=namespace)
    with client.context():
        yield
