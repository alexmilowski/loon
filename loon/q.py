import sys
import redis
import argparse
from redisgraph import Graph

def q(graph,query):
   return graph.query(query)

def current_article(graph):
   q = 'match (n:Article) return n order by n.datePublished desc limit 1'
   result = graph.query(q)
   return result.result_set[0][0] if len(result.result_set)>0 else None

def article_by_published(graph,date):
   q = 'match (n:Article {{datePublished: "{date}"}}) return n'.format(date=date)
   result = graph.query(q)
   return result.result_set[0][0] if len(result.result_set)>0 else None

def following_article(graph,date,limit):
   q = 'match (n:Article) where n.datePublished > "{date}" return n limit {limit}'.format(date=date,limit=limit)
   result = graph.query(q)
   return result.result_set[0][0] if len(result.result_set)>0 else None

def preceding_article(graph,date,limit):
   q = 'match (n:Article) where n.datePublished < "{date}" return n order by n.datePublished desc limit {limit} '.format(date=date,limit=limit)
   result = graph.query(q)
   return result.result_set[0][0] if len(result.result_set)>0 else None

def article_by_id(graph,article_id):
   q = 'match (n:Article {{id: "{article_id}"}}) return n'.format(article_id=article_id)
   result = graph.query(q)
   return result.result_set[0][0] if len(result.result_set)>0 else None

def article_keywords(graph,article_id):
   q = """
match (n:Article {{id: "{article_id}"}})
match (n)-[:LabeledWith]->(k)
return k.text""".format(article_id=article_id)
   result = graph.query(q)
   print(result.result_set)
   return map(lambda row : row[0],result.result_set) if len(result.result_set)>0 else None

def content_location(graph,article_id):
   q = """
match (n:Article {{id: "{article_id}"}})
match (n)-[:AssociatedMedia]->(r)
return r.url""".format(article_id=article_id)
   result = graph.query(q)
   return result.result_set[0][0] if len(result.result_set)>0 else None

def keywords(graph):
   q = 'match (a:Article)-[r:LabeledWith]->(n:Keyword) return n.text,count(r)'
   result = graph.query(q)
   return result.result_set

def labeled_with(graph,*keywords):
   k = ''
   a = 'match (a:Article)\n'
   for index,keyword in enumerate(keywords):
      k += 'match (r{index}:Keyword {{text: "{keyword}"}})\n'.format(index=index,keyword=keyword)
      a += 'match (a)-[:LabeledWith]->(r{index})\n'.format(index=index)
   q = k + a + 'return a.id,a.datePublished,a.headline,a.description'
   result = graph.query(q)
   return result.result_set

def main(call_args=None):
   argparser = argparse.ArgumentParser(description='Query')
   argparser.add_argument('--host',help='Redis host',default='0.0.0.0')
   argparser.add_argument('--port',help='Redis port',type=int,default=6379)
   argparser.add_argument('graph',help='The graph name')
   argparser.add_argument('name',help='The query name')
   argparser.add_argument('args',nargs='*',help='The query arguments')

   args = argparser.parse_args(call_args if call_args is not None else sys.argv)

   r = redis.Redis(host=args.host,port=args.port)
   graph = Graph(args.graph,r)

   if args.name=='q':
      for query in args.args:
         result = q(graph,query)
         result.pretty_print()
   elif args.name=='current':
      result = current_article(graph)
      print(result)
   elif args.name=='published':
      for published in args.args:
         result = article_by_published(graph,published)
         print(result)
   elif args.name=='id':
      for article_id in args.args:
         result = article_by_id(graph,article_id)
         print(result)
   elif args.name=='keywords_for':
      for article_id in args.args:
         result = article_keywords(graph,article_id)
         print(list(result))
   elif args.name=='location':
      for article_id in args.args:
         result = content_location(graph,article_id)
         print(result)
   elif args.name=='keywords':
      for keyword,count in keywords(graph):
         print('{}: {}'.format(keyword,str(count)))
   elif args.name=='labeled_with':
      if len(args.args)>0:
         result = labeled_with(graph,*args.args)
         for entry in result:
            print(' '.join(entry))
   elif args.name=='following' or args.name=='preceding':
      if len(args.args)==0:
         current = current_article(graph)
         date = current.properties['datePublished']
      else:
         date = args.args[0]
      limit = int(args.args[1]) if len(args.args)>2 else 1
      result = following_article(graph,date,limit) if args.name=='following' else preceding_article(graph,date,limit)
      print(result)
   else:
      sys.stderr.write('Unknown query: '+args.name+'\n')
      sys.exit(1)

if __name__ == '__main__':
   main()
