from flask import Flask, g, Blueprint, request, render_template_string, abort, send_file, redirect, current_app, send_from_directory, Response, stream_with_context, after_this_request
import sys
import requests
import gzip
import functools
import argparse
import logging
from io import StringIO
import redis
from redisgraph import Graph

from loon import current_article, following_article, preceding_article, article_by_published, article_by_id, article_keywords, content_location, keywords, labeled_with

def get_graph():
   if 'graph' not in g:
      r = redis.Redis(host=current_app.config['REDIS_HOST'],port=int(current_app.config['REDIS_PORT']))
      g.graph = Graph(current_app.config['GRAPH'],r)
   return g.graph


def gzipped(f):
   @functools.wraps(f)
   def view_func(*args, **kwargs):
      @after_this_request
      def zipper(response):
         if not current_app.config.get('COMPRESS'):
            return response

         accept_encoding = request.headers.get('Accept-Encoding', '')

         if 'gzip' not in accept_encoding.lower():
            return response

         response.direct_passthrough = False

         if (response.status_code < 200 or
             response.status_code >= 300 or
             'Content-Encoding' in response.headers):
            return response
         gzip_buffer = BytesIO()
         gzip_file = gzip.GzipFile(mode='wb',
                                   fileobj=gzip_buffer)
         gzip_file.write(response.data)
         gzip_file.close()

         response.data = gzip_buffer.getvalue()
         response.headers['Content-Encoding'] = 'gzip'
         response.headers['Vary'] = 'Accept-Encoding'
         response.headers['Content-Length'] = len(response.data)

         return response

      return f(*args, **kwargs)

   return view_func

def getResourceText(url):
   req = requests.get(url)
   if (req.status_code == 200):
      contentType = req.headers.get('Content-Type')
      encoding = 'UTF-8'
      if contentType is not None:
         param = contentType.find('charset=')
         if param>0:
            encoding = contentType[param+8:]
      text = req.content.decode(encoding)
      return text
   else:
      raise IOError('Cannot get <{}>, status={}'.format(uri,req.status_code))


def generate_template(config,base):
   options = config.get('TEMPLATE_OPTIONS')
   output = StringIO()
   output.write('{{% extends "{}" %}}\n'.format(base))
   if options is not None:
      for name in options:
         output.write('{{% block {} %}}\n'.format(name))
         output.write(options[name])
         output.write('\n{% endblock %}\n')
   return output.getvalue()

def siteURL(config,request):
   u = current_app.config.get('SITE_URL')
   return u if u is not None else request.url_root[0:-1]

def entry_from_node(node):
   entry = node.properties
   datePublished = entry['datePublished']
   entry['date'],entry['time'] = datePublished.split('T')
   entry['path'] = "/journal/entry/{}/".format(datePublished)
   return entry

def renderEntry(entry,base=None,path=None):
   try:

      article_id = entry['id']

      url = content_location(get_graph(),article_id)

      datePublished = entry['datePublished']
      following = following_article(get_graph(),datePublished,1)
      if following is not None:
         following = entry_from_node(following)
      preceding = preceding_article(get_graph(),datePublished,1)
      if preceding is not None:
         preceding = entry_from_node(preceding)

      content = getResourceText(url)

      labels = list(article_keywords(get_graph(),article_id))
      labels = sorted(labels if labels is not None else [],key=str.lower)

      topics = keywords(get_graph())
      sortedTopics = sorted(topics,key=lambda x : str.lower(x[0]))
      return render_template_string(
         generate_template(current_app.config,'base.html'),
         siteURL=siteURL(current_app.config,request),
         path=path,
         entry=entry,
         entryContent=content,
         preceding=preceding,
         following=following,
         keywords=labels,
         topics=topics,
         base=base)
   except FileNotFoundError:
      abort(404)

def renderKeyword(keyword,entries):
   try:
      return render_template_string(generate_template(current_app.config,'keyword.html'),entry=None,keyword=keyword,entries=entries)
   except FileNotFoundError:
      abort(404)

logger = logging.getLogger('webapp')

blog = Blueprint('loon_blog',__name__,template_folder='templates')

@blog.route('/')
@gzipped
def index():

   currentEntry = current_article(get_graph())
   if currentEntry is None:
      abort(404)

   return renderEntry(entry_from_node(currentEntry))

@blog.route('/journal/entry/<dateTime>/')
@gzipped
def entryByTime(dateTime):

   currentEntry = article_by_published(get_graph(),dateTime)
   if currentEntry is None:
      abort(404)

   return renderEntry(entry_from_node(currentEntry))

@blog.route('/journal/entry/<dateTime>/<path:path>')
@gzipped
def entryMedia(dateTime,path):

   base = content_location(get_graph(),date=dateTime)
   if base is None:
      abort(404)

   base = base.rsplit('/',1)[0]
   uri = base + '/' + path
   req = requests.get(uri, stream = True)
   return Response(stream_with_context(req.iter_content(20*1024)), content_type = req.headers['content-type'])

@blog.route('/rel/keyword/<keyword>')
@gzipped
def relKeyword(keyword):

   entries = map(
      lambda row : {'id':row[0],'datePublished':row[1],'headline':row[2],'description':row[3],'path':"/journal/entry/{}/".format(row[1])},
      labeled_with(get_graph(),keyword ) )

   return renderKeyword(keyword,entries)

@blog.errorhandler(404)
def page_not_found(error):
   return render_template_string(generate_template(current_app.config,'error.html'), siteURL=siteURL if siteURL is not None else request.url_root[0:-1], path=request.path, entry=None, error="I'm sorry.  I can't find that page.")


assets = Blueprint('loon_assets',__name__)
@assets.route('/assets/<path:path>')
@gzipped
def send_asset(path):
   dir = current_app.config.get('ASSETS')
   if dir is None:
      dir = __file__[:__file__.rfind('/')] + '/assets/'
   return send_from_directory(dir, path)

def create_app(host='0.0.0.0',port=6379,graph='test',app=None):
   if app is None:
      app = Flask(__name__)
   app.register_blueprint(blog)
   app.register_blueprint(assets)
   if 'REDIS_HOST' not in app.config:
      app.config['REDIS_HOST'] = host
   if 'REDIS_PORT' not in app.config:
      app.config['REDIS_PORT'] = port
   if 'GRAPH' not in app.config:
      app.config['GRAPH'] = graph
   return app

def main(call_args=None):
   argparser = argparse.ArgumentParser(description='Web')
   argparser.add_argument('--host',help='Redis host',default='0.0.0.0')
   argparser.add_argument('--port',help='Redis port',type=int,default=6379)
   argparser.add_argument('--config',help='configuration file')
   argparser.add_argument('graph',help='The graph name')
   args = argparser.parse_args(call_args if call_args is not None else sys.argv)

   app = create_app(host=args.host,port=args.port,graph=args.graph)
   if args.config is not None:
      import os
      app.config.from_pyfile(os.path.abspath(args.config))
   app.run()

if __name__ == '__main__':
   main()
