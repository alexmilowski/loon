import sys
import os
import redis
import argparse
from redisgraph import Graph

def main(call_args=None):

   argparser = argparse.ArgumentParser(description='Article importer')
   argparser.add_argument('--extension',nargs='?',help='The source file extension',default='cypher')
   argparser.add_argument('--host',help='Redis host',default='0.0.0.0')
   argparser.add_argument('--port',help='Redis port',type=int,default=6379)
   argparser.add_argument('graph',help='The graph name')
   argparser.add_argument('dir',nargs='+',help='The directories to process.')

   args = argparser.parse_args(call_args if call_args is not None else sys.argv)

   print('Connecting to '+args.host+':'+str(args.port)+' for graph '+args.graph)
   r = redis.Redis(host=args.host,port=args.port)

   graph = Graph(args.graph,r)

   for dir in args.dir:
      for root, dirs, files in os.walk(dir):
         for file in files:
            if file.rsplit('.',1)[-1]==args.extension:
               query = root + os.sep + file
               print(query)

               with open(query) as query_source:
                  q = query_source.read()
                  result = graph.query(q)

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
