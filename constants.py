DATASET_DIR = 'audio/LibriSpeechSamples/'

BATCH_NUM_TRIPLETS = 6  # the number of triples. note the batch size = number of triples * 3 * number_of_slices

# very dumb values. I selected them to have a blazing fast training.
# we will change them to their true values (to be defined?) later.
# this value is ignored during training, which will be set to the number of frame slices of the first random wav

NUM_FRAMES = 2

# 8K or 16K
SAMPLE_RATE = 16000

# CONSIDER increasing to 2 seconds

TRUNCATE_SOUND_FIRST_SECONDS = 1

CHECKPOINT_FOLDER = 'checkpoints'
