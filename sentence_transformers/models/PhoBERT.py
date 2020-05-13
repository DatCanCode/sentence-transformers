from torch import Tensor
from torch import nn
from transformers import RobertaModel
from .tokenizer.PhoTokenizer import PhoTokenizer
import json
from typing import Union, Tuple, List, Dict, Optional
import os
import logging

class PhoBERT(nn.Module):
    """PhoBERT model to generate token embeddings.

    Each token is mapped to an output vector from PhoBERT.
    """
    def __init__(self, model_name_or_path: str, max_seq_length: int = 128, do_lower_case: Optional[bool] = False, model_args: Dict = {}, tokenizer_args: Dict = {}):
        super(PhoBERT, self).__init__()
        self.config_keys = ['max_seq_length', 'do_lower_case']
        self.do_lower_case = do_lower_case

        if max_seq_length > 256:
            logging.warning("PhoBERT only allows a max_seq_length of 256 (258 with special tokens). Value will be set to 256")
            max_seq_length = 256
        self.max_seq_length = max_seq_length

        if self.do_lower_case is not None:
            tokenizer_args['do_lower_case'] = do_lower_case

        self.phobert = RobertaModel.from_pretrained(model_name_or_path, **model_args)
        self.tokenizer = PhoTokenizer.load(model_name_or_path, **tokenizer_args)


    def forward(self, features):
        """Returns token_embeddings, cls_token"""
        output_states = self.roberta(**features)
        output_tokens = output_states[0]
        cls_tokens = output_tokens[:, 0, :]  # CLS token is first token
        features.update({'token_embeddings': output_tokens, 'cls_token_embeddings': cls_tokens, 'attention_mask': features['attention_mask']})

        if len(output_states) > 2:
            features.update({'all_layer_embeddings': output_states[2]})

        return features

    def get_word_embedding_dimension(self) -> int:
        return self.roberta.config.hidden_size

    def tokenize(self, text: str) -> List[int]:
        """
        Tokenizes a text and maps tokens to token-ids
        """
        return self.tokenizer.convert_tokens_to_ids(self.tokenizer.tokenize(text))

    def get_sentence_features(self, tokens: List[int], pad_seq_length: int):
        """
        Convert tokenized sentence in its embedding ids, segment ids and mask

        :param tokens:
            a tokenized sentence
        :param pad_seq_length:
            the maximal length of the sequence. Cannot be greater than self.sentence_transformer_config.max_seq_length
        :return: embedding ids, segment ids and mask for the sentence
        """
        pad_seq_length = min(pad_seq_length, self.max_seq_length) + 2 ##Add Space for CLS + SEP token
        return self.tokenizer.prepare_for_model(tokens, max_length=pad_seq_length, pad_to_max_length=True, return_tensors='pt')

    def get_config_dict(self):
        return {key: self.__dict__[key] for key in self.config_keys}

    def save(self, output_path: str):
        self.roberta.save_pretrained(output_path)
        self.tokenizer.save(output_path)

        with open(os.path.join(output_path, 'sentence_phobert_config.json'), 'w') as fOut:
            json.dump(self.get_config_dict(), fOut, indent=2)

    @staticmethod
    def load(input_path: str):
        config_path = os.path.join(input_path, 'sentence_phobert_config.json')
        if os.path.exists(config_path):
            with open(config_path) as fIn:
                config = json.load(fIn)
        else:
            config = {}
        return PhoBERT(model_name_or_path=input_path, **config)