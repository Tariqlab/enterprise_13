# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

import dateutil.parser
import base64
import hmac
import hashlib
import requests
import uuid
import time
import xml.etree.ElementTree as XmlElementTree

from odoo import models, fields, api, _
from odoo.exceptions import UserError, AccessError
from odoo.addons.iap import jsonrpc
from werkzeug.urls import url_join, url_quote


class SocialMediaTwitter(models.Model):
    _inherit = 'social.media'

    _TWITTER_ENDPOINT = 'https://api.twitter.com'

    media_type = fields.Selection(selection_add=[('twitter', 'Twitter')])

    def action_add_account(self):
        """ Builds the URL to Twitter in order to allow account access, then redirects the client.
        Redirect is done in 'self' since Twitter will then return back to the app with the 'oauth_callback' param.

        Redirect URI from Twitter will land on this module controller's 'twitter_account_callback' method.

        We raise an error message if request_token endpoint is not successfull.
        (Most likely reason for that to happen: the callback URI is not correctly defined in the Twitter APP settings) """

        self.ensure_one()

        if self.media_type != 'twitter':
            return super(SocialMediaTwitter, self).action_add_account()

        twitter_consumer_key = self.env['ir.config_parameter'].sudo().get_param('social.twitter_consumer_key')
        twitter_consumer_secret_key = self.env['ir.config_parameter'].sudo().get_param('social.twitter_consumer_secret_key')
        if twitter_consumer_key and twitter_consumer_secret_key:
            return self._add_twitter_accounts_from_configuration()
        else:
            return self._add_twitter_accounts_from_iap()

    def _add_twitter_accounts_from_configuration(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        twitter_oauth_url = url_join(self._TWITTER_ENDPOINT, "oauth/request_token")

        headers = self._get_twitter_oauth_header(
            twitter_oauth_url,
            headers={'oauth_callback': url_join(base_url, "social_twitter/callback")}
        )
        response = requests.post(twitter_oauth_url, headers=headers)
        if response.status_code != 200:
            raise UserError(self._extract_error_message(response))

        response_values = {
            response_value.split('=')[0]: response_value.split('=')[1]
            for response_value in response.text.split('&')
        }

        twitter_authorize_url = url_join(self._TWITTER_ENDPOINT, 'oauth/authorize')

        return {
            'name': 'Add Account',
            'type': 'ir.actions.act_url',
            'url': twitter_authorize_url + '?oauth_token=' + response_values['oauth_token'],
            'target': 'self'
        }

    def _add_twitter_accounts_from_iap(self):
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        social_iap_endpoint = self.env['ir.config_parameter'].sudo().get_param(
            'social.social_iap_endpoint',
            self.env['social.media']._DEFAULT_SOCIAL_IAP_ENDPOINT
        )

        iap_add_accounts_url = requests.get(url_join(social_iap_endpoint, 'iap/social_twitter/add_accounts'), params={
            'returning_url': url_join(base_url, 'social_twitter/callback'),
            'db_uuid': self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        }).text

        if iap_add_accounts_url == 'unauthorized':
            raise UserError(_("You don't have an active subscription. Please buy one here: %s") % 'https://www.odoo.com/buy')
        elif iap_add_accounts_url == 'wrong_configuration':
            raise UserError(_("The url that this service requested returned an error. Please contact the author of the app."))

        return {
            'type': 'ir.actions.act_url',
            'url': iap_add_accounts_url,
            'target': 'self'
        }

    def _extract_error_message(self, response):
        """ This method tries to extract the error code of the response.
        Code '415' simply means that the user has not correctly configured his Twitter account
        so we help him by displaying a nice error message with what he needs to do.

        If we can't parse the document or if the code is different, we return the raw response text value. """

        try:
            document_root = XmlElementTree.fromstring(response.text)
            error_node = document_root.find('error')
            if error_node is not None and error_node.get('code') == '415':
                base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
                return _('You need to add the following callback URL to your twitter application settings: %s'
                         % url_join(base_url, "social_twitter/callback"))
        except XmlElementTree.ParseError:
            pass

        return response.text

    def _get_twitter_oauth_header(self, url, headers={}, params={}, method='POST'):
        """ Twitter needs parameters to contain a 'oauth_signature'.
        This signature requires that all the headers and params are encoded inside it. """

        twitter_consumer_key = self.env['ir.config_parameter'].sudo().get_param('social.twitter_consumer_key')
        header_params = {
            'oauth_nonce': uuid.uuid4(),
            'oauth_consumer_key': twitter_consumer_key,
            'oauth_signature_method': 'HMAC-SHA1',
            'oauth_timestamp': str(int(time.time())),
            'oauth_version': '1.0',
        }
        oauth_token_secret = headers.pop('oauth_token_secret', '')
        header_params.update(headers)

        signature_params = {}
        signature_params.update(header_params)
        signature_params.update(params)
        header_params['oauth_signature'] = self._get_twitter_oauth_signature(
            method,
            url,
            signature_params,
            oauth_token_secret=oauth_token_secret
        )
        header_oauth = 'OAuth ' + ', '.join([('%s="%s"' % (key, url_quote(header_params[key], unsafe='+:/'))) for key in sorted(header_params.keys())])
        return {'Authorization': header_oauth}

    def _get_twitter_oauth_signature(self, method, url, params, oauth_token_secret=''):
        """ Special signature handling as requested by Twitter.
        For more info: https://developer.twitter.com/en/docs/basics/authentication/guides/creating-a-signature.html """

        self.ensure_one()

        twitter_consumer_secret_key = self.env['ir.config_parameter'].sudo().get_param('social.twitter_consumer_secret_key')
        if twitter_consumer_secret_key:
            return self._get_twitter_oauth_signature_from_configuration(method, url, params, twitter_consumer_secret_key, oauth_token_secret)
        else:
            return self._get_twitter_oauth_signature_from_iap(method, url, params, oauth_token_secret)

    def _get_twitter_oauth_signature_from_configuration(self, method, url, params, twitter_consumer_secret_key, oauth_token_secret=''):
        signing_key = '&'.join([twitter_consumer_secret_key, oauth_token_secret])
        base_string = '&'.join([
            method,
            url_quote(url, unsafe='+:/'),
            url_quote('&'.join([
                ('%s=%s' % (url_quote(key, unsafe='+:/'), url_quote(params[key], unsafe='+:/')))
                for key in sorted(params.keys())
            ]), unsafe='+:/')
        ])

        signed_sha1 = hmac.new(bytes(signing_key, 'utf-8'), bytes(base_string, 'utf-8'), hashlib.sha1).digest()
        return base64.b64encode(signed_sha1).decode('ascii')

    def _get_twitter_oauth_signature_from_iap(self, method, url, params, oauth_token_secret=''):
        params['oauth_nonce'] = str(params['oauth_nonce'])
        json_params = {
            'method': method,
            'url': url,
            'params': params,
            'oauth_token_secret': oauth_token_secret,
            'db_uuid': self.env['ir.config_parameter'].sudo().get_param('database.uuid')
        }
        social_iap_endpoint = self.env['ir.config_parameter'].sudo().get_param(
            'social.social_iap_endpoint',
            self.env['social.media']._DEFAULT_SOCIAL_IAP_ENDPOINT
        )
        try:
            return jsonrpc(url_join(social_iap_endpoint, 'iap/social_twitter/get_signature'), params=json_params)
        except AccessError:
            return None

    @api.model
    def _format_tweet(self, tweet):
        """ Formats a tweet returned by the Twitter API to a dict that will be interpreted by our frontend. """
        formatted_tweet = {
            'id': tweet.get('id_str'),
            'message': tweet.get('full_text'),
            'from': {
                'id': tweet.get('user').get('id_str'),
                'name': tweet.get('user').get('name'),
                'profile_image_url_https': tweet.get('user').get('profile_image_url_https')
            },
            'created_time': tweet.get('created_at'),
            'formatted_created_time': self.env['social.stream.post']._format_published_date(fields.Datetime.from_string(
                dateutil.parser.parse(tweet.get('created_at')).strftime('%Y-%m-%d %H:%M:%S')
            )),
            'user_likes': tweet.get('favorited'),
            'likes': {
                'summary': {
                    'total_count': tweet.get('favorite_count')
                }
            },
        }

        attachment = False
        attached_medias = tweet.get('extended_entities', {}).get('media', [])
        if attached_medias:
            if attached_medias[0].get('type') == 'photo':
                attachment = {
                    'type': 'photo',
                    'media': {
                        'image': {
                            'src': attached_medias[0].get('media_url_https')
                        }
                    }
                }

        if attachment:
            formatted_tweet['attachment'] = attachment

        return formatted_tweet
