import hashlib
import json
import string
from functools import wraps

import os
import re
import markdown
import bcrypt  # sudo apt-get install libffi-dev
from flask import (Flask, render_template, flash, redirect, url_for, request, Response,
                   abort)
from flask.ext.wtf import Form
from wtforms import (BooleanField, TextField, TextAreaField)
from wtforms.validators import (InputRequired, ValidationError)
from flask.ext.script import Manager


CONF_FILE = 'config.json'
password_cache = []

app = Flask(__name__)


def load_config():
    config = {}
    try:
        save_flag = False
        with open(CONF_FILE, 'r') as f:
            config = json.loads(f.read())
        # Verify passwords are hashed, re-save config w/ hashed PWs if not
        for user, password in config.get('USERS', {}).iteritems():
            user = str(user)
            password = str(password)
            if password[:7] != "$2a$12$":
                save_flag = True
                config['USERS'][user] = bcrypt.hashpw(str(password), bcrypt.gensalt())
            if user != user.lower():  # Make username lowercase if not already
                save_flag = True
                config['USERS'][user.lower()] = config['USERS'].pop(user)

        if save_flag:
            print('Updating config file...')
            with open(CONF_FILE, 'w') as f:
                f.write(json.dumps(config, indent=True))
    except Exception as e:
        print(str(e) + '\n\n Error loading ' + CONF_FILE + '! \n\n')

    return config


app.config.update(load_config())
app.debug = app.config.get('DEBUG', False)
manager = Manager(app)


def check_auth(username, password):
    try:
        user = str(username).lower()
        pwd = str(password)
        shahash = hashlib.sha1(user + pwd).hexdigest()  # If attacker can read RAM, well game over anyway
        if shahash in password_cache:
            return True
        else:
            hashed = str(app.config['USERS'].get(user, ''))
            if bcrypt.hashpw(pwd, hashed) == hashed:
                password_cache.append(shahash)
                return True
    except Exception as e:
        print e
        return False


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return Response('Please log in.', 401, {'WWW-Authenticate': 'Basic realm="Login Required"'})
        return f(*args, **kwargs)

    return decorated


class Processors(object):
    def __init__(self, content=""):
        self.content = content

    def wikilink(self, html):
        """Processes Wikilink syntax "[[Link]]" within content body.  This is
        intended to be run after the content has been processed by Markdown.

        Args:
            html (str): Post-processed HTML output from Markdown

        Kwargs:
            None

        Syntax: This accepts Wikilink syntax in the form of [[WikiLink]] or
        [[url/location|LinkName]].  Everything is referenced from the base
        location "/", therefore sub-pages need to use the
        [[page/subpage|Subpage]].
        """
        link = r"((?<!\<code\>)\[\[([^<].+?) \s*([|] \s* (.+?) \s*)?]])"
        compLink = re.compile(link, re.X | re.U)
        for i in compLink.findall(html):
            title = [i[-1] if i[-1] else i[1]][0]
            url = self.clean_url(i[1])
            formattedLink = u"<a href='{0}'>{1}</a>".format(url_for('display', url=url), title)
            html = re.sub(compLink, formattedLink, html, count=1)
        return html

    def clean_url(self, url):
        pageStub = re.sub('[ ]{2,}', ' ', url).strip()
        pageStub = pageStub.lower().replace(' ', '_')
        pageStub = pageStub.replace('\\\\', '/').replace('\\', '/')
        valid_characters = string.ascii_letters + string.digits + '_' + '-' + '/'
        pageStub = ''.join(c for c in pageStub if c in valid_characters)
        return pageStub

    def out(self):
        """Final content output.  Processes the Markdown, post-processes, and
        Meta data.
        """
        md = markdown.Markdown(['codehilite', 'fenced_code', 'meta', 'tables'])
        html = md.convert(self.content)
        phtml = self.wikilink(html)
        body = self.content.split('\n\n', 1)[1]
        meta = md.Meta
        return phtml, body, meta


class Page(object):
    def __init__(self, path, url, new=False):
        self.path = path
        self.url = url
        self._meta = {}
        if not new:
            self.load()
            self.render()

    def load(self):
        with open(self.path, 'rU') as f:
            self.content = f.read().decode('utf-8')

    def render(self):
        processed = Processors(self.content)
        self._html, self.body, self._meta = processed.out()

    def save(self, update=True):
        folder = os.path.dirname(self.path)
        if not os.path.exists(folder):
            os.makedirs(folder)
        with open(self.path, 'w') as f:
            for key, value in self._meta.items():
                line = u'%s: %s\n' % (key, value)
                f.write(line.encode('utf-8'))
            f.write('\n'.encode('utf-8'))
            f.write(self.body.replace('\r\n', '\n').encode('utf-8'))
        if update:
            self.load()
            self.render()

    @property
    def meta(self):
        return self._meta

    def __getitem__(self, name):
        item = self._meta[name]
        if len(item) == 1:
            return item[0]
        print(item)
        return item

    def __setitem__(self, name, value):
        self._meta[name] = value

    @property
    def html(self):
        return self._html

    def __html__(self):
        return self.html

    @property
    def title(self):
        try:
            return self['title']
        except KeyError:
            return self.url

    @title.setter
    def title(self, value):
        self['title'] = value

    @property
    def tags(self):
        try:
            return self['tags']
        except KeyError:
            return ""

    @tags.setter
    def tags(self, value):
        self['tags'] = value


class Wiki(object):
    def __init__(self, root):
        self.root = root

    def path(self, url):
        return os.path.join(self.root, url + '.md')

    def exists(self, url):
        path = self.path(url)
        return os.path.exists(path)

    def get(self, url):
        path = os.path.join(self.root, url + '.md')
        if self.exists(url):
            return Page(path, url)
        return None

    def get_or_404(self, url):
        page = self.get(url)
        if page:
            return page
        abort(404)

    def get_bare(self, url):
        path = self.path(url)
        if self.exists(url):
            return False
        return Page(path, url, new=True)

    def move(self, url, newurl):
        os.rename(
            os.path.join(self.root, url) + '.md',
            os.path.join(self.root, newurl) + '.md'
        )

    def delete(self, url):
        path = self.path(url)
        if not self.exists(url):
            return False
        print(path)
        os.remove(path)
        return True

    def index(self):
        def _walk(directory, path_prefix=()):
            for name in os.listdir(directory):
                fullname = os.path.join(directory, name)
                if os.path.isdir(fullname):
                    _walk(fullname, path_prefix + (name,))
                elif name.endswith('.md'):
                    if not path_prefix:
                        url = name[:-3]
                    else:
                        url = os.path.join(os.path.join(*path_prefix), name[:-3])
                    pages.append(Page(fullname, url.replace('\\', '/')))

        pages = []
        _walk(self.root)
        return sorted(pages, key=lambda x: x.title.lower())

    def get_tags(self):
        pages = self.index()
        tags = {}
        for page in pages:
            pagetags = page.tags.split(',')
            for tag in pagetags:
                tag = tag.strip()
                if tag == '':
                    continue
                elif tags.get(tag):
                    tags[tag].append(page)
                else:
                    tags[tag] = [page]
        return tags

    def index_by_tag(self, tag):
        pages = self.index()
        tagged = []
        for page in pages:
            if tag in page.tags:
                tagged.append(page)
        return sorted(tagged, key=lambda x: x.title.lower())

    def search(self, term, ignore_case=True, attrs=['title', 'tags', 'body']):
        pages = self.index()
        regex = re.compile(term, re.IGNORECASE if ignore_case else 0)
        matched = []
        for page in pages:
            for attr in attrs:
                if regex.search(getattr(page, attr)):
                    matched.append(page)
                    break
        return matched


class URLForm(Form):
    url = TextField('', [InputRequired()])

    def validate_url(form, field):
        if wiki.exists(field.data):
            raise ValidationError('The URL "%s" exists already.' % field.data)

    def clean_url(self, url):
        return Processors().clean_url(url)


class SearchForm(Form):
    term = TextField('', [InputRequired()])
    ignore_case = BooleanField(description='Ignore Case', default=app.config.get('DEFAULT_SEARCH_IGNORE_CASE', True))


class EditorForm(Form):
    title = TextField('', [InputRequired()])
    body = TextAreaField('', [InputRequired()])
    tags = TextField('')


wiki = Wiki(app.config.get('CONTENT_DIR'))


@app.route('/')
@requires_auth
def home():
    page = wiki.get('home')
    if page:
        return display('home')
    return render_template('home.html')


@app.route('/index/')
@requires_auth
def index():
    pages = wiki.index()
    return render_template('index.html', pages=pages)


@app.route('/<path:url>/')
@requires_auth
def display(url):
    page = wiki.get_or_404(url)
    return render_template('page.html', page=page)


@app.route('/create/', methods=['GET', 'POST'])
@requires_auth
def create():
    form = URLForm()
    if form.validate_on_submit():
        return redirect(url_for('edit', url=form.clean_url(form.url.data)))
    return render_template('create.html', form=form)


@app.route('/edit/<path:url>/', methods=['GET', 'POST'])
@requires_auth
def edit(url):
    page = wiki.get(url)
    form = EditorForm(obj=page)
    if not form.title.data:
        form.title.data = url
    if form.validate_on_submit():
        if not page:
            page = wiki.get_bare(url)
        form.populate_obj(page)
        page.save()
        flash('"%s" was saved.' % page.title, 'success')
        return redirect(url_for('display', url=url))
    return render_template('editor.html', form=form, page=page)


@app.route('/preview/', methods=['POST'])
@requires_auth
def preview():
    a = request.form
    data = {}
    processed = Processors(a['body'])
    data['html'], data['body'], data['meta'] = processed.out()
    return data['html']


@app.route('/move/<path:url>/', methods=['GET', 'POST'])
@requires_auth
def move(url):
    page = wiki.get_or_404(url)
    form = URLForm(obj=page)
    if form.validate_on_submit():
        newurl = form.url.data
        wiki.move(url, newurl)
        return redirect(url_for('.display', url=newurl))
    return render_template('move.html', form=form, page=page)


@app.route('/delete/<path:url>/', methods=['POST'])
@requires_auth
def delete(url):
    page = wiki.get_or_404(url)
    wiki.delete(url)
    flash('Page "%s" was deleted.' % page.title, 'success')
    return redirect(url_for('home'))


@app.route('/tags/')
@requires_auth
def tags():
    tags = wiki.get_tags()
    return render_template('tags.html', tags=tags)


@app.route('/tag/<string:name>/')
@requires_auth
def tag(name):
    tagged = wiki.index_by_tag(name)
    return render_template('tag.html', pages=tagged, tag=name)


@app.route('/search/', methods=['GET', 'POST'])
@requires_auth
def search():
    form = SearchForm()
    if form.validate_on_submit():
        results = wiki.search(form.term.data, form.ignore_case.data)
        return render_template('search.html', form=form,
                               results=results, search=form.term.data)
    return render_template('search.html', form=form, search=None)


@app.errorhandler(404)
def page_not_found(e):
    print(e)
    return render_template('404.html'), 404


if __name__ == '__main__':
    manager.run()