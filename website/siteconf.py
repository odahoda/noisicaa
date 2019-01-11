import hashlib

import odasite
import odasite.blog

class Site(odasite.Site):
    def configure(self):
        ignore = ['*~', '.#*', '*.pyc', 'README.md']
        self.add_collector(odasite.FileCollector('.', ignore=ignore))

        default_context = {
            'staticfile': self.__staticfile,
        }

        jinja2_engine = odasite.Jinja2Engine(
            site=self,
            template_dir='templates',
            default_context=default_context)

        blog = odasite.blog.Blog(
            source_root='blog',
            post_renderer=jinja2_engine.get_renderer('blog-post.html'),
            index_renderer=jinja2_engine.get_renderer('blog-index.html'),
            archive_renderer=jinja2_engine.get_renderer('blog-archive.html'),
        )
        blog.setup(self)

        self.add_classifier(odasite.Classifier(
            odasite.StaticFile,
            'css/*', 'img/*', 'js/*',
            'robots.txt'))
        self.add_classifier(odasite.Classifier(
            odasite.MarkdownFile, '*.md',
            renderer=jinja2_engine.get_renderer('page.html'),
            typogrify=True))

        self.add_remote(odasite.RSyncRemote(
            host='odahoda.de',
            user='pink',
            directory='/srv/clients/odahoda/de.odahoda.noisicaa/htdocs/'))

    def __staticfile(self, path):
        h = hashlib.md5()
        with open(self.basedir / path, 'rb') as fp:
            h.update(fp.read())
        return '/%s?v=%s' % (path, h.hexdigest())
