python_library(
  name='3rdparty',
  dependencies=['3rdparty:boto', '3rdparty:argparse']
)

python_library(
  name='lib',
  sources=globs('*.py'),
  dependencies=[':3rdparty']
)

python_binary(
  name='backup-monkey',
  entry_point='cli:run',
  dependencies=[':lib']
)
