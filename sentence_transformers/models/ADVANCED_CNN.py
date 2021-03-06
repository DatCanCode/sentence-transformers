import torch
from torch import nn, Tensor
import torch.nn.functional as F
from typing import Union, Tuple, List, Iterable, Dict
import logging
import gzip
from tqdm import tqdm
import numpy as np
import os
import json
from ..util import import_from_string, fullname, http_get
from .tokenizer import WordTokenizer, WhitespaceTokenizer


class CNN(nn.Module):
    """CNN-layer with multiple kernel-sizes over the word embeddings"""

    def __init__(self, in_word_embedding_dimension: int, out_channels: int = 256, kernel_sizes: List[int] = [1, 3, 5]):
        nn.Module.__init__(self)
        self.config_keys = ['in_word_embedding_dimension', 'out_channels', 'kernel_sizes']
        self.in_word_embedding_dimension = in_word_embedding_dimension
        self.out_channels = out_channels
        self.kernel_sizes = kernel_sizes

        self.embeddings_dimension = out_channels*len(kernel_sizes)
        self.convsModule = nn.ModuleList()
        self.pooling = nn.AvgPool1d(2, stride=2)
        in_channels = in_word_embedding_dimension
        
        for _ in range(4):
            self.convsModule.append(nn.ModuleList())

        for kernel_size in kernel_sizes:
            padding_size = int((kernel_size - 1) / 2)
            conv = nn.Conv1d(in_channels=in_channels, out_channels=out_channels, kernel_size=kernel_size,
                             padding=padding_size)
            for i in self.convsModule:
                i.append(conv)

    def forward(self, features):
        token_embeddings = features['all_layer_embeddings']
        vectors =[]
        for idx, convs in enumerate(self.convsModule):
            temp = []
            token_embedding = token_embeddings[len(token_embeddings)-idx-1].transpose(1, -1)
            for conv in convs:
                a = F.tanh(conv(token_embedding))
                a = a.transpose(1, -1)
                a = self.pooling(a)
                a = a.transpose(1, -1)
                temp.append(a)
            vectors.append(torch.cat(temp, 1))

        out = torch.cat(vectors, 1).transpose(1, -1)
        features.update({'token_embeddings': out})
        return features

    def get_word_embedding_dimension(self) -> int:
        return self.embeddings_dimension

    def tokenize(self, text: str) -> List[int]:
        raise NotImplementedError()

    def save(self, output_path: str):
        with open(os.path.join(output_path, 'cnn_config.json'), 'w') as fOut:
            json.dump(self.get_config_dict(), fOut, indent=2)

        torch.save(self.state_dict(), os.path.join(output_path, 'pytorch_model.bin'))

    def get_config_dict(self):
        return {key: self.__dict__[key] for key in self.config_keys}

    @staticmethod
    def load(input_path: str):
        with open(os.path.join(input_path, 'cnn_config.json'), 'r') as fIn:
            config = json.load(fIn)

        weights = torch.load(os.path.join(input_path, 'pytorch_model.bin'))
        model = CNN(**config)
        model.load_state_dict(weights)
        return model