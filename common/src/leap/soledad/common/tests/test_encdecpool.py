# -*- coding: utf-8 -*-
# test_encdecpool.py
# Copyright (C) 2015 LEAP
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <http://www.gnu.org/licenses/>.
"""
Tests for encryption and decryption pool.
"""
import json

from twisted.internet.defer import inlineCallbacks
from twisted.trial.unittest import TestCase

from leap.soledad.client.encdecpool import SyncEncrypterPool
from leap.soledad.client.encdecpool import SyncDecrypterPool

from leap.soledad.common.document import SoledadDocument
from leap.soledad.common.tests.util import BaseSoledadTest


DOC_ID = "mydoc"
DOC_REV = "rev"
DOC_CONTENT = {'simple': 'document'}

class TestSyncEncrypterPool(TestCase, BaseSoledadTest):

    def setUp(self):
        BaseSoledadTest.setUp(self)
        crypto = self._soledad._crypto
        sync_db = self._soledad._sync_db
        self._pool = SyncEncrypterPool(crypto, sync_db)
        self._pool.start()

    def tearDown(self):
        self._pool.stop()
        BaseSoledadTest.tearDown(self)

    @inlineCallbacks
    def test_get_encrypted_doc_returns_none(self):
        doc = yield self._pool.get_encrypted_doc(DOC_ID, DOC_REV)
        self.assertIsNone(doc)

    @inlineCallbacks
    def test_enqueue_doc_for_encryption_and_get_encrypted_doc(self):
        doc = SoledadDocument(
            doc_id=DOC_ID, rev=DOC_REV, json=json.dumps(DOC_CONTENT))
        self._pool.enqueue_doc_for_encryption(doc)

        # exhaustivelly attempt to get the encrypted document
        encrypted = None
        attempts = 0
        while encrypted is None and attempts < 10:
            encrypted = yield self._pool.get_encrypted_doc(DOC_ID, DOC_REV)
            attempts += 1
        
        self.assertIsNotNone(encrypted)
        self.assertTrue(attempts < 10)

class TestSyncDecrypterPool(TestCase, BaseSoledadTest):

    def _insert_doc_cb(self, doc, gen, trans_id):
        self._inserted_docs.append((doc, gen, trans_id))

    def setUp(self):
        BaseSoledadTest.setUp(self)
        # setup the pool
        self._pool = SyncDecrypterPool(
            self._soledad._crypto,
            self._soledad._sync_db,
            source_replica_uid=self._soledad._dbpool.replica_uid,
            insert_doc_cb=self._insert_doc_cb)
        # reset the inserted docs mock
        self._inserted_docs = []

    def tearDown(self):
        if self._pool.running:
            self._pool.stop()
        BaseSoledadTest.tearDown(self)

    def test_insert_received_doc(self):
        self._pool.start(1)
        self._pool.insert_received_doc(
           DOC_ID, DOC_REV, "{}", 1, "trans_id", 1)

        def _assert_doc_was_inserted(_):
            self.assertEqual(
                self._inserted_docs,
                [(SoledadDocument(DOC_ID, DOC_REV, "{}"), 1, u"trans_id")])

        self._pool.deferred.addCallback(_assert_doc_was_inserted)
        return self._pool.deferred

    def test_insert_received_doc_many(self):
        many = 100
        self._pool.start(many)

        for i in xrange(many):
            gen = idx = i + 1
            doc_id = "doc_id: %d" % idx
            rev = "rev: %d" % idx
            content = {'idx': idx}
            trans_id = "trans_id: %d" % idx
            self._pool.insert_received_doc(
                doc_id, rev, content, gen, trans_id, idx)

        def _assert_doc_was_inserted(_):
            self.assertEqual(many, len(self._inserted_docs))
            idx = 1
            for doc, gen, trans_id in self._inserted_docs:
                expected_gen = idx
                expected_doc_id = "doc_id: %d" % idx
                expected_rev = "rev: %d" % idx
                expected_content = json.dumps({'idx': idx})
                expected_trans_id = "trans_id: %d" % idx

                self.assertEqual(expected_doc_id, doc.doc_id)
                self.assertEqual(expected_rev, doc.rev)
                self.assertEqual(expected_content, json.dumps(doc.content))
                self.assertEqual(expected_gen, gen)
                self.assertEqual(expected_trans_id, trans_id)

                idx += 1

        self._pool.deferred.addCallback(_assert_doc_was_inserted)
        return self._pool.deferred
