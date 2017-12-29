"""
   filename                             chapter_id speaker_id dataset_id
0  1272/128104/1272-128104-0000.wav     128104       1272  dev-clean
1  1272/128104/1272-128104-0001.wav     128104       1272  dev-clean
2  1272/128104/1272-128104-0002.wav     128104       1272  dev-clean
3  1272/128104/1272-128104-0003.wav     128104       1272  dev-clean
4  1272/128104/1272-128104-0004.wav     128104       1272  dev-clean
5  1272/128104/1272-128104-0005.wav     128104       1272  dev-clean
6  1272/128104/1272-128104-0006.wav     128104       1272  dev-clean
7  1272/128104/1272-128104-0007.wav     128104       1272  dev-clean
8  1272/128104/1272-128104-0008.wav     128104       1272  dev-clean
9  1272/128104/1272-128104-0009.wav     128104       1272  dev-clean
"""
import logging

import numpy as np
import pandas as pd
from python_speech_features import fbank, delta

import constants as c
from constants import SAMPLE_RATE
from librispeech_wav_reader import read_audio


#def normalize_frames(m):
#    return [(v - np.mean(v)) / np.std(v) for v in m]
def normalize_frames(m,epsilon=1e-12):
    # normalize per frame
    return [(v - np.mean(v)) / max(np.std(v),epsilon) for v in m]

def pre_process_inputs(signal=np.random.uniform(size=32000), target_sample_rate=8000):
    # sample rate: 8K or 16K, default 16K
    filter_banks, energies = fbank(signal, samplerate=target_sample_rate, nfilt=64, winlen=0.025)
    delta_1 = delta(filter_banks, N=1)
    delta_2 = delta(delta_1, N=1)

    filter_banks = normalize_frames(filter_banks)
    delta_1 = normalize_frames(delta_1)
    delta_2 = normalize_frames(delta_2)

    frames_features = np.hstack([filter_banks, delta_1, delta_2])
    num_frames = len(frames_features)
    network_inputs = []
    for j in range(8, num_frames - 8):
        frames_slice = frames_features[j - 8:j + 8]
        # one slice = one input = 16 frames each with 64*3 features
        # 16*2*32*3, why reshape? 16,64,3 should be good enough?
        # TODO: change the shape to 16,64,3, will need to update the model as well
        network_inputs.append(np.reshape(frames_slice, (32, 32, 3)))
    # number_of_slice, 32, 32,3
    return np.array(network_inputs)


# TODO: remove this hot fix when the model supports dynamic number of frame slices
def pad_with_copy_if_needed(x,min_global_frames):
    x_padded = [x]
    x_len = len(x)
    x_padded_len = x_len
    while x_padded_len < min_global_frames:
        x_padded.append(x)
        x_padded_len += x_len
    if len(x_padded) == 1:
        return x
    else:
        return np.concatenate(x_padded)

class MiniBatch:
    def __init__(self, libri, batch_size):
        # indices = np.random.choice(len(libri), size=batch_size, replace=False)
        # [anc1, anc2, anc3, pos1, pos2, pos3, neg1, neg2, neg3]
        # [sp1, sp2, sp3, sp1, sp2, sp3, sp4, sp5, sp6]

        unique_speakers = list(libri['speaker_id'].unique())
        # batch_size = number of triples
        num_triplets = batch_size

        anchor_batch = None
        positive_batch = None
        negative_batch = None
        for ii in range(num_triplets):
            # select a pair of speakers
            two_different_speakers = np.random.choice(unique_speakers, size=2, replace=False)
            anchor_positive_speaker = two_different_speakers[0]
            negative_speaker = two_different_speakers[1]
            # select 2 files for the first speaker
            anchor_positive_file = libri[libri['speaker_id'] == anchor_positive_speaker].sample(n=2, replace=False)
            anchor_df = pd.DataFrame(anchor_positive_file[0:1])
            anchor_df['training_type'] = 'anchor'
            positive_df = pd.DataFrame(anchor_positive_file[1:2])
            positive_df['training_type'] = 'positive'
            # select 1 file for the second speaker
            negative_df = libri[libri['speaker_id'] == negative_speaker].sample(n=1)
            negative_df['training_type'] = 'negative'

            if anchor_batch is None:
                anchor_batch = anchor_df.copy()
            else:
                anchor_batch = pd.concat([anchor_batch, anchor_df], axis=0)

            if positive_batch is None:
                positive_batch = positive_df.copy()
            else:
                positive_batch = pd.concat([positive_batch, positive_df], axis=0)

            if negative_batch is None:
                negative_batch = negative_df.copy()
            else:
                negative_batch = pd.concat([negative_batch, negative_df], axis=0)

        self.libri_batch = pd.DataFrame(pd.concat([anchor_batch, positive_batch, negative_batch], axis=0))
        self.audio_loaded = False
        self.num_triplets = num_triplets

    def load_wav(self):
        # load a batch of wave files
        self.libri_batch['raw_audio'] = self.libri_batch['filename'].apply(lambda x: read_audio(x))
        min_global_frames = c.TRUNCATE_SOUND_FIRST_SECONDS * c.SAMPLE_RATE
        # TODO: remove this hot fix when the model supports dynmaic number of frame slices
        self.libri_batch['raw_audio'] = self.libri_batch['raw_audio'].apply(lambda x: pad_with_copy_if_needed(x,min_global_frames))

        min_existing_frames = min(self.libri_batch['raw_audio'].apply(lambda x: len(x)).values)
        max_frames = min(min_global_frames, min_existing_frames)
        self.libri_batch['raw_audio'] = self.libri_batch['raw_audio'].apply(lambda x: x[0:max_frames])
        self.audio_loaded = True

    def to_inputs(self):

        if not self.audio_loaded:
            self.load_wav()

        x = self.libri_batch['raw_audio'].values
        new_x = []
        for sig in x:
            new_x.append(pre_process_inputs(sig, target_sample_rate=SAMPLE_RATE))
        # x has a shape: batch_size*3, number_of_slices, 32,32,3
        x = np.array(new_x)
        y = self.libri_batch['speaker_id'].values
        logging.info('x.shape = {}'.format(x.shape))
        logging.info('y.shape = {}'.format(y.shape))

        # anchor examples [speakers] == positive examples [speakers]
        np.testing.assert_array_equal(y[0:self.num_triplets], y[self.num_triplets:2 * self.num_triplets])

        return x, y


def stochastic_mini_batch(libri, batch_size):
    mini_batch = MiniBatch(libri, batch_size)
    return mini_batch


def main():
    from librispeech_wav_reader import read_librispeech_structure
    libri = read_librispeech_structure(c.DATASET_DIR)
    stochastic_mini_batch(libri, 3)


if __name__ == '__main__':
    main()
