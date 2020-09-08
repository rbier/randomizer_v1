The **Randomization Management Tool** is a Django web app, configured to run on Heroku, that allows multiple centers to randomize study participants to placebo vs experimental drugs, using permuted block randomization, while maintaining researcher blinding.

# Installation

## Setting up the RMT on your local machine

To use the RMT, you will need the following installed on your local machine:

* [Git](https://docs.github.com/en/github/getting-started-with-github/set-up-git)

* [Python3](https://www.python.org/downloads/)

* [Venv](https://docs.python.org/3/library/venv.html)

Once those are installed, you can then download the RMT code using the “Code” dropdown on github. To get the RMT up and running locally, you will need to:

1. Start up a local virtual environment via venv

2. Go to the directory where the RMT code resides

3. Run `pip install -r requirements.txt`

4. Set up a database. The current system uses Postgres, but if you want to use something more lightweight for testing, you can use SQLite. To do so, run `pip install sqlite3` and update your `randomizer/settings.py` with the `DATABASE` value set as follows:

```
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': os.path.join(BASE_DIR, 'db.sqlite3'),
    }
}
```

5. Create a secret key (see section below)

6. Run `python manage.py migrate`

7. Run `python manage.py createsuperuser` and follow the instructions to create your default user

8. Run `python manage.py runserver`

Your local instance of the RMT will now be available at `http://localhost:8000`.

## Setting up the RMT on a Heroku account

The RMT is configured for launch on Heroku, a cloud platform that lets you launch webapps quickly and easily. If you are using a randomization with less than a thousand subjects, it is possible to run the entire RMT system for free using a dev account with a single Dyno and the Heroku Postgres add-on (used as your database). To start:

1. Create a [Heroku account](https://signup.heroku.com/dc)

2. Create a new app (via the “new” dropdown in the top right)

3. In your new project, update your add-ons to include Heroku Postgres via the Resources tab 

Note that you will need to upgrade your Free Dyno to either a Hobby ($7/mo) or Standard ($25/mo) Dyno type if you want your system to be always running, and you will need to upgrade your Postgres to be a Hobby Basic instance ($9/mo) or Standard 0 ($50/mo) for studies with more than a thousand subjects, or for multiple studies.

### Setting up the Heroku environment
You will need to set some Heroku “Config Vars” which will be used in the Django environment. The following config vars are used:
 
|Key|Potential values|Description|Required|
|---|----------------|-----------|--------|
|HEROKU|Any non-blank|Tells app to apply settings from Heroku|Yes|
|secret_key|Secret|App secret key, see section below|Yes|
|slack_token|Secret|Used for Slack integration, see section below|No|
|sentry_dsn|Secret|Used for Sentry integration, see section below|No|

### Deploying Code to Heroku
Once the above settings are configured, deploy using your local git checkout of the RMT as described [here](https://devcenter.heroku.com/articles/git). Once this is complete, run `heroku run python manage.py createsuperuser` and follow the instructions to create your default user. At this point, you should be ready to visit your website on herokuapp.com and start performing randomizations.

## Creating a unique secret key

Every Django project needs a [SECRET_KEY](https://docs.djangoproject.com/en/2.2/ref/settings/#std:setting-SECRET_KEY) for cryptographic signing. You can set this in your environment via the `secret_key` environment variable. It is also possible to hard code this in your `randomizer/settings.py`; this is not recommended if you plan on sharing your code, as any person with access to this variable can work around many of Django’s security protections.

To generate a secret_key, run the following script:

```
from django.core.management.utils import get_random_secret_key
print(get_random_secret_key())
```

## (Optional) Hooking up Slack for access request notifications

[Slack](https://slack.com/) is a communication platform that can allow us to send notifications to a channel when a user has created an account or requested access to a research study. If you wish to receive these notifications, create a new app following Slack’s [instructions](https://api.slack.com/authentication/basics). When you attempt to install the app you will receive a slack token. Copy this token and paste it into the `slack_token` environment variable. It is also possible to hard code this in your `randomizer/settings.py`; this is not recommended if you plan on sharing your code, as any person with access to this variable will be able to send messages to your Slack channel.

## (Optional) Setting up Sentry for error notifications

[Sentry](https://sentry.io/) is an error and performance monitoring tool that integrates well with Django. Any errors that occur on the system can trigger a notification via email or Slack integration. The RMT already supports Sentry, and only needs a project key to be set up. To create a project key, create a free Sentry account click the “Projects” navigation bar item, then click “create project.” Choose a Django project and give the project a name.

Creating a Django project in Sentry will provide some boilerplate code, which is already included in the RMT except for the data source name (DSN) unique to your project. Copy the data source name (which should look like `https://xxxx@xxxx.ingest.sentry.io/xxxx`) and paste it into the `sentry_dsn` environment variable. It is also possible to hard code this in your `randomizer/settings.py`; this is not recommended if you plan on sharing your code, as any person with access to this variable can send events to your Sentry account.

# Getting Started

## Setting up your first study as an administrator

TBD

## Setting up your account as a researcher at a center

TBD

## Randomizing patients

TBD

# Administrative tasks

## Sharing study access codes with other centers

TBD

## Approving requests for researchers to join as part of a center

TBD

## Cancelling/confirming a patient for a center

TBD

## Adding additional centers to a study

TBD

## Renaming table columns

TBD

## Advanced features using the admin panel

TBD
