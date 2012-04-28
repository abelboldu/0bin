# -*- coding: utf-8 -*-

import os
import hashlib
import json

from datetime import datetime, timedelta

import settings


class Paste(object):
    """
        A paste objet to deal with the file opening/parsing/saving and the
        calculation of the expiration date.
    """

    DIR_CACHE = set()

    DURATIONS = {
        u'1_day': 24 * 3600,
        u'1_month': 30 * 24 * 3600,
        u'never': 365 * 24 * 3600 * 100,
    }


    def __init__(self, uuid=None, content=None,
                 expiration=None,
                 comments=None):

        self.content = content
        self.expiration = expiration
        self.comments = comments

        if isinstance(self.content, unicode):
           self.content = self.content.encode('utf8')

        self.expiration = self.get_expiration(expiration)

        self.uuid = uuid or hashlib.sha1(self.content).hexdigest()


    def get_expiration(self, expiration):
        """
            Return a tuple with the date at which the Paste will expire
            or if it should be destroyed after first reading.

            Do not modify the value if it's already a date object or
            if it's burn_after_reading
        """

        if (isinstance(expiration, datetime) or
            'burn_after_reading' in str(expiration)):
            return expiration

        try:
            return datetime.now() + timedelta(seconds=self.DURATIONS[expiration])
        except KeyError:
            return u'burn_after_reading'


    @classmethod
    def build_path(cls, *dirs):
        """
            Generic static content path builder. Return a path to
            a location in the static content file dir.
        """
        return os.path.join(settings.PASTE_FILES_ROOT, *dirs)


    @classmethod
    def get_path(cls, uuid):
        """
            Return the file path of a paste given uuid
        """
        return cls.build_path(uuid[:2], uuid[2:4], uuid)


    @property
    def path(self):
        """
            Return the file path for this path. Use get_path().
        """
        return self.get_path(self.uuid)


    @classmethod
    def load_from_file(cls, path):
        """
            Return an instance of the paste object with the content of the
            given file.
        """
        try:
            paste = open(path)
            uuid = os.path.basename(path)
            expiration = paste.next().strip()
            content = paste.next().strip()
            comments = paste.read()[:-1] # remove the last coma
            if "burn_after_reading" not in str(expiration):
                expiration = datetime.strptime(expiration,'%Y-%m-%d %H:%M:%S.%f')

        except StopIteration:
            raise TypeError(u'File %s is malformed' % path)
        except (IOError, OSError):
            raise ValueError(u'Can not open paste from file %s' % path)

        return Paste(uuid=uuid, comments=comments,
                     expiration=expiration, content=content)


    @classmethod
    def load(cls, uuid):
        """
            Return an instance of the paste object with the content of the
            file matching this uuid. Use load_from_file() and get_path()
        """
        return cls.load_from_file(cls.get_path(uuid))


    def save(self):
        """
            Save the content of this paste to a file.

            If comments are passed, they are expected to be serialized
            already.
        """
        head, tail = self.uuid[:2], self.uuid[2:4]

        # the static files are saved in project_dir/static/xx/yy/uuid
        # xx and yy are generated from the uuid (see get_path())
        # we need to check if they are created before writting
        # but since we want to prevent to many writes, we create
        # an in memory cache that will hold the result of this check fo
        # each worker. If the dir is not in cache, we check the FS, and
        # if the dir is not in there, we create the dir
        if head not in self.DIR_CACHE:

            self.DIR_CACHE.add(head)

            if not os.path.isdir(self.build_path(head)):
                os.makedirs(self.build_path(head, tail))
                self.DIR_CACHE.add((head, tail))

            elif (head, tail) not in self.DIR_CACHE:
                path = self.build_path(head, tail)
                self.DIR_CACHE.add((head, tail))
                if not os.path.isdir(path):
                    os.mkdir(path)

        # add a timestamp to burn after reading to allow
        # a quick period of time where you can redirect to the page without
        # deleting the paste
        if self.expiration == "burn_after_reading":
            self.expiration = self.expiration + '#%s' % datetime.now()

        # writethe paste
        with open(self.path, 'w') as f:
            f.write(unicode(self.expiration) + '\n')
            f.write(self.content + '\n')
            if self.comments:
                f.write(comments)

        return self


    def delete(self):
        """
            Delete the paste file.
        """
        os.remove(self.path)


    @classmethod
    def add_comment_to(cls, uuid, **comment):
        """
            Append a comment to the file of the paste with the given uuid.
            The comment is serialized to json, and a comma is added at the
            end of it. Then the result is appended to the paste file.
            This way we can add sequencially all comments to the file by just
            appending to it, and then extracting the comment by selecting
            this big blob of text, adding [] around it and use it as a json list
            with no extra processing.
        """
        with open(cls.get_path(uuid), 'a') as f:
            f.write(json.dumps(comment) + u',\n')


    def add_comment(self, **comment):
        """
            Append a comment to the file of this paste.

            Use add_comment_to()
        """
        self.add_comment_to(self.uuid, **comment)