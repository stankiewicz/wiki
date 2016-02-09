# Readme

## About
As I wanted a wiki that just uses plain markdown files as backend, that is easy
to use and that is written in python, to enable me to easily hack around,
but found nothing, I just wrote this down. I hope that it might help others ,too.

## Features

* Markdown Syntax Editing
* Tags
* Regex Search
* Random URLs
* Web Editor
* Pages can also be edited manually, possible uses are:
	* use the cli
	* use your favorite editor
	* sync with dropbox
	* and many more
* Easily themable

### New additions

* Speed Improvements
	* Code Optimizations
	* Caching
* Wikilinks-Support
* Access protection (for private wikis)


## Setup
Just clone this repository, cd into it, run:

	pip install -r requirements.txt

You might need to install some packages such as python-dev and libffi-dev: 

	sudo apt-get install libffi-dev python-dev

You may create `content/` dir in the directory or one will be created automatically
upon start.

The configuration file is `config.json`. Set the SECURITY_KEY to an empty string
and a new one will be auto-generated. To enable auth, set "AUTH" to true. To add
new users, modify or extend the sample users in the file. Set the password to a 
plain text string, and it will be hashed using bcrypt (and the config file updated) 
when the Wiki is restarted. Note: the sample users have passwords of 'password', so 
change the passwords or remove the users. 

To reiterate, to set passwords, specify a plain text password and it will be updated 
with a bcrypt hash when the Wiki is started or restarted.

If you want your `config.json` file in your `content/` dir, modify the source of app.py,
it is specified on line 17 (or thereabouts).

## Start
Afterwards just run the app however you want. I personally recommend something
like gunicorn (which is included in the requirements.txt):
	
	# Activate your virtualenv, e.g.,
	source bin/activate
	
	# Start up gunicorn
	gunicorn app:app
	
Note: by default, gunicorn runs on 127.0.0.1:8000. To customize, use the form: 

	gunicorn -b 127.0.0.1:8000 app:app 

You can install `setproctitle` with pip to get meaningful process names.

If you just want to try something out or debug something, you can execute
the app with `python app.py` which will run the development server in debug
mode. There's a debug flag in the config file as well.

## Theming
The templates are based on jinja2. I used
[bootstrap](http://twitter.github.com/bootstrap/) for the design.
If you want to change the overall design, you should edit `templates/base.html`
and/or `static/bootstrap.css`. If you do not like specific parts of the site,
it should be fairly easy to find the equivalent template and edit it.

## Contributors

Thank you very much to my two top contributers @walkerh and @traeblain. You two have posted so many issues and especially solved them with so many pull requests, that I sometimes lose track of it! :)
