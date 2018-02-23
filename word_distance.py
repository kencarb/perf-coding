# calculate minimum distance between two words in a list
#

class WordDistanceFinder(object):
  def __init__(self, words):
    self.words = words

  def minDistance(self, first, second):
    tmp_dist = 0
    min_dist = -1
    f_flg = False
    s_flg = False
    for x in range(0, len(self.words)):
      if self.words[x] == first:
        f_idx = x
        f_flg = True
      if self.words[x] == second:
        s_idx = x
        s_flg = True
      if f_flg and s_flg:
        min_dist = abs(f_idx - s_idx)
        if tmp_dist == 0 or min_dist < tmp_dist:
          tmp_dist = min_dist
    return min_dist

def main():
  arr = ["the", "quick", "brown", "fox", "jumped", "over", "the", "lazy", "lazy", "dog"]
  #first = 'the'
  first = 'lazy'
  #second = 'dog'
  second = 'lazy'
  #second = 'bob'

  wf = WordDistanceFinder(arr)
  dist = wf.minDistance(first, second)
  print("word list:")
  print(str(arr))
  print("result:")
  if dist == -1:
    print("one or both of the words '{}' and '{}' are not found".format(first,second))
  else:
    print("min dist between '{}' and '{}' is {}".format(first,second,str(dist)))

if __name__ == '__main__':
  main()
