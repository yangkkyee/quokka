# coding: utf-8

from flask import request, session, redirect, current_app, url_for
from flask.ext.security.utils import login_user

from .models import User, Connection


def get_oauth_app(provider):
    provider_name = "oauth_" + provider
    return getattr(current_app, provider_name)


def oauth_login(provider):
    oauth_app = get_oauth_app(provider)
    return oauth_app.authorize(
        callback=url_for(
            '{0}_authorized'.format(provider),
            _external=True,
            next=request.args.get('next', request.referrer) or None
        )
    )


def make_oauth_handler(provider):

    def oauth_handler(resp):
        app = current_app
        oauth_app = get_oauth_app(provider)

        oauth_app.tokengetter(
            lambda: session.get("oauth_" + provider + "_token")
        )

        if resp is None:
            return 'Access denied: reason=%s error=%s' % (
                request.args['error_reason'],
                request.args['error_description']
            )
        session["oauth_" + provider + "_token"] = (resp['access_token'], '')
        data = app.config.get("OAUTH", {}).get(provider)
        me = oauth_app.get(data.get('_info_endpoint'))

        if not any([me.data.get('verified'),
                    me.data.get('verified_email')]):
            return "Access denied: email not verified"

        email = me.data.get('email')
        name = me.data.get('name')
        provider_user_id = me.data.get('id')
        profile_url = me.data.get('link')

        access_token = resp['access_token']

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            user = User(
                name=name,
                email=email,
                username=User.generate_username(email)
            )
            user.save()

        try:
            connection = Connection.objects.get(
                user_id=str(user.id),
                provider_id=provider,
            )
            connection.access_token = access_token
            connection.save()
        except Connection.DoesNotExist:
            connection = Connection(
                user_id=str(user.id),
                provider_id=provider,
                provider_user_id=provider_user_id,
                profile_url=profile_url,
                access_token=access_token
            )
            connection.save()

        login_user(user)

        next = request.args.get(
            'next', request.referrer
        ) or session.get(
            'next'
        ) or app.config.get('OAUTH_POST_LOGIN', "/")

        return redirect(next)
    return oauth_handler
