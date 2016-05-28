#!/usr/bin/env python2
# -*- coding: utf-8-*-
import wave
import json
import tempfile
import logging
import urllib
import urlparse
import requests
from jasper import plugin

class WatsonSTTPlugin(plugin.STTPlugin):
    """
    Speech-To-Text implementation which relies on the IBM Watson Speech-To-Text
    API. This requires an IBM Bluemix account, but the first 1000 minutes of
    transcribing per month are free.

    To obtain a login:
    1. Register for IBM Bluemix here:
       https://console.ng.bluemix.net/registration/
    2. Once you've logged in, click the "Use Services & APIs" link on the
       dashboard
    3. Click the "Speech To Text" icon
    4. In the form on the right, leave all options as defaults and click Create
    5. You'll now have a new service listed on your dashboard. If you click
       that service there will be a navigation option for "Service Credentials"
       in the left hand nav. Find your username and password there.

    Excerpt from sample profile.yml:

        ...
        timezone: US/Pacific
        stt_engine: watson
        watson:
            username: $YOUR_USERNAME_HERE
            password: $YOUR_PASSWORD_HERE

    """

    def __init__(self, *args, **kwargs):
        plugin.STTPlugin.__init__(self, *args, **kwargs)

        # FIXME: get init args from config
        """
        Arguments:
        username - the watson api username credential
        password - the watson api password credential
        """
        self._logger = logging.getLogger(__name__)
        self._username = None
        self._password = None
        self._http = requests.Session()
        try:
            language = self.profile['language']
        except KeyError:
            language = 'en-US'

        self.language = language.lower()
 
        self.username =  self.profile['watson']['username']
        self.password = self.profile['watson']['password']

    @property
    def request_url(self):
        return self._request_url

    @property
    def username(self):
        return self._username

    @username.setter
    def username(self, value):
        self._username = value

    @property
    def password(self):
        return self._password

    @password.setter
    def password(self, value):
        self._password = value

    def transcribe(self, fp):
        """
        Performs STT via the Watson Speech-to-Text API, transcribing an audio
        file and returning an English string.

        Arguments:
        fp -- the path to the .wav file to be transcribed
        """

        if not self.username:
            self._logger.critical('Username missing, transcription request ' +
                                  'aborted.')
            return []
        elif not self.password:
            self._logger.critical('Password missing, transcription ' +
                                  'request aborted.')
            return []

        wav = wave.open(fp, 'rb')
        frame_rate = wav.getframerate()
        wav.close()
        data = fp.read()

        headers = {'content-type':
                   'audio/l16; rate=%s; channels=1' % frame_rate}
        r = self._http.post(
            'https://stream.watsonplatform.net/' +
            'speech-to-text/api/v1/recognize?continuous=true',
            data=data, headers=headers, auth=(self.username, self.password)
        )
        try:
            r.raise_for_status()
        except requests.exceptions.HTTPError as e:
            self._logger.critical('Request failed with http status %d',
                                  r.status_code)
            if r.status_code == requests.codes['forbidden']:
                self._logger.warning('Status 403 is probably caused by ' +
                                     'invalid credentials.')
            return []
        r.encoding = 'utf-8'
        try:
            response = r.json()
            if len(response['results']) == 0:
                # Response result is empty
                raise ValueError('Nothing has been transcribed.')
            results = [alt['transcript'] for alt
                       in response['results'][0]['alternatives']]
        except ValueError as e:
            self._logger.warning('Empty response: %s', e.args[0])
            results = []
        except (KeyError, IndexError):
            self._logger.warning('Cannot parse response.', exc_info=True)
            results = []
        else:
            # Convert all results to uppercase
            results = tuple(result.strip().upper() for result in results)
            self._logger.info('Transcribed: %r', results)
        return results


