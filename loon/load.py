import sys
import os
import redis
import argparse
from redisgraph import Graph
from yamlblog import Article, generate_string

def isoformat(s):
   return s if type(s)==str else s.isoformat()

def main(call_args=None):

   argparser = argparse.ArgumentParser(description='Article importer')
   argparser.add_argument('--extension',nargs='?',help='The source file extension (md or yaml for yablog; cypher for direct cypher)',default='cypher')
   argparser.add_argument('--host',help='Redis host',default='0.0.0.0')
   argparser.add_argument('--port',help='Redis port',type=int,default=6379)
   argparser.add_argument('--password',help='Redis password')
   argparser.add_argument('--weburi',help='The article base web uri (e.g., http://example.com/journal/entry/)')
   argparser.add_argument('--entryuri',help='The article source base uri (e.g., http://example.github.io/journal/)')
   argparser.add_argument('--show-query',help='Show the cypher queries before they are run.',action='store_true',default=False)
   argparser.add_argument('graph',help='The graph name')
   argparser.add_argument('dir',nargs='+',help='The directories to process.')

   args = argparser.parse_args(call_args if call_args is not None else sys.argv)

   print('Connecting to '+args.host+':'+str(args.port)+' for graph '+args.graph)
   r = redis.Redis(host=args.host,port=args.port,password=args.password)

   graph = Graph(args.graph,r)

   extension = '.' + args.extension if args.extension[0]!='.' else args.extension
   extension_count = extension.count('.')
   extension = extension.rsplit('.')[-extension_count:]

   if args.weburi is not None and args.weburi[-1]!='/':
      args.weburi += '/'
   if args.entryuri is not None and args.entryuri[-1]!='/':
      args.entryuri += '/'

   is_cypher = extension==['cypher']

   for dir in args.dir:
      prefix_len = len(dir)
      for root, dirs, files in os.walk(dir):
         for file in files:

            current_path = root[prefix_len:]
            if len(current_path)>0:
               current_path += '/'

            fparts = file.rsplit('.',extension_count)
            if fparts[-extension_count:]==extension:
               base = fparts[0]
               source = root + os.sep + file
               print(source)

               if is_cypher:
                  with open(source) as query_source:
                     query = query_source.read()
                  if args.show_query:
                     print(query)
                  result = graph.query(query)
               else:
                  # assume yablog
                  with open(source) as article_source:
                     article = Article(article_source)
                  resource = args.weburi + isoformat(article.metadata['published']) if args.weburi is not None and 'published' in article.metadata else None
                  entry = args.entryuri + current_path + base + '.html' if args.entryuri is not None else None

                  query = generate_string(article,'text/x.cypher',resource=resource,source=entry)
                  if args.show_query:
                     print(query)
                  result = graph.query(query)


               print("""
               runtime: {runtime}ms
               nodes: +{n_added},-{n_deleted}
               relationships: +{r_added},-{r_deleted}
               labels: +{l_added}
               properties: +{p_added}
               indices: +{i_added},-{i_deleted}
               """.format(
                  runtime=result.run_time_ms,
                  n_added=result.nodes_created,
                  n_deleted=result.nodes_deleted,
                  r_added=result.relationships_created,
                  r_deleted=result.relationships_deleted,
                  l_added=result.labels_added,
                  p_added=result.properties_set,
                  i_added=result.indices_created,
                  i_deleted=result.indices_deleted
               ))

if __name__ == '__main__':
   main()
