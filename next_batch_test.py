import unittest
from next_batch import pad_with_copy_if_needed
import numpy as np
class MyTestCase(unittest.TestCase):
    def test_pad_with_copy_if_needed(self):
        x=np.array([1,2])
        pad_with_copy_if_needed(x, 1)
        self.assertTrue(np.all(np.equal(x,pad_with_copy_if_needed(x, 1))))
        self.assertTrue(np.all(np.equal(np.array([1,2,1,2]),pad_with_copy_if_needed(x, 3))))

if __name__ == '__main__':
    unittest.main()
