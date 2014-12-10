# -*- coding: utf-8 -*-

import os
import asyncio

import aiohttp

from tornado import web

from waterbutler import settings
from waterbutler.providers.core import RequestWrapper
from waterbutler.server.handlers import core
from waterbutler.server.utils import coroutine


STREAM_METHODS = ('PUT', 'POST')
ACTION_MAP = {
    'GET': 'download',
    'PUT': 'upload',
    'DELETE': 'delete',
}


@web.stream_request_body
class CRUDHandler(core.BaseHandler):

    @coroutine
    def prepare(self):
        yield from super().prepare()
        self.arguments['action'] = ACTION_MAP[self.request.method]
        self.prepare_stream()

    def prepare_stream(self):
        if self.request.method in STREAM_METHODS:
            self.obj = RequestWrapper(self.request)
            self.uploader = self.provider.upload(self.obj, **self.arguments)
        else:
            self.obj = None

    def data_received(self, chunk):
        """Note: Only called during uploads."""
        if self.obj:
            self.obj.content.feed_data(chunk)

    @coroutine
    def get(self):
        """Download a file."""
        result = yield from self.provider.download(**self.arguments)
        _, file_name = os.path.split(self.arguments['path'])
        self.set_header('Content-Type', result.content_type)
        self.set_header('Content-Disposition', 'attachment; filename=' + file_name)
        while True:
            chunk = yield from result.content.read(settings.CHUNK_SIZE)
            if not chunk:
                break
            self.write(chunk)

    @coroutine
    def put(self):
        """Upload a file."""
        self.obj.content.feed_eof()
        result = yield from self.uploader
        self.set_status(result.response.status)

    @coroutine
    def delete(self):
        """Delete a file."""
        result = yield from self.provider.delete(**self.arguments)
        self.set_status(result.response.status)

    def on_connection_close(self):
        if self.request.method in STREAM_METHODS:
            self.obj.content.feed_eof()