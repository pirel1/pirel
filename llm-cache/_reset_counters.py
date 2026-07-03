from pathlib import Path


if __name__ == '__main__':
  cwd = Path(__file__).parent
  for counter_fpath in cwd.glob('*-counter.json'):
    counter_fpath.write_text('0')
