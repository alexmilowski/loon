
import importlib
import sys

from .load import main

def main():
   if len(sys.argv)<2:
      sys.stderr.write('You must specify a command (e.g. load) as the first argument.')
      sys.exit(1)
   name = sys.argv[1]
   current_module = __loader__.name.rsplit('.',1)[0]
   module_name = current_module + '.' + name if name.find('.')<0 else name
   program = __import__(module_name,globals(),locals(),['main'],0)
   program.main(call_args=sys.argv[2:])

if __name__ == '__main__':
   main()
