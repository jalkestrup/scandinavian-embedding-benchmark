import random
from collections.abc import Iterable
from itertools import islice
from typing import Any, TypeVar

import datasets
from mteb.abstasks import AbsTaskClustering

T = TypeVar("T")


def batched(iterable: Iterable[T], n: int) -> Iterable[tuple[T, ...]]:
    # batched('ABCDEFG', 3) --> ABC DEF G
    if n < 1:
        raise ValueError("n must be at least one")
    it = iter(iterable)
    while batch := tuple(islice(it, n)):
        yield batch


class VGClustering(AbsTaskClustering):
    @property
    def description(self) -> dict[str, Any]:
        return {
            "name": "VGClustering",
            "hf_hub_name": "navjordj/VG_summarization",
            "description": "Articles and ingresses from VG news articles extracted from Norsk Aviskorpus. Uses articles classes as clusters.",
            "reference": "https://huggingface.co/datasets/navjordj/VG_summarization",
            "type": "Clustering",
            "category": "p2p",
            "eval_splits": ["test"],
            "eval_langs": ["nb"],
            "main_score": "v_measure",
            "revision": "d4c5a8ba10ae71224752c727094ac4c46947fa29",
        }

    def load_data(self, **kwargs: dict):  # noqa: ARG002
        """
        Load dataset from HuggingFace hub
        """
        if self.data_loaded:
            return

        self.dataset: datasets.DatasetDict = datasets.load_dataset(
            self.description["hf_hub_name"],
            revision=self.description.get("revision"),
        )  # type: ignore

        self.dataset_transform()
        self.data_loaded = True

    def dataset_transform(self):
        splits = self.description["eval_splits"]

        documents = []
        labels = []
        label_col = "classes"

        ds = {}
        for split in splits:
            ds_split = self.dataset[split]

            _label = self.normalize_labels(ds_split[label_col])
            documents.extend(ds_split["title"])
            labels.extend(_label)

            documents.extend(ds_split["ingress"])
            labels.extend(_label)

            documents.extend(ds_split["article"])
            labels.extend(_label)

            assert len(documents) == len(labels)

            rng = random.Random(1111)  # local only seed
            # resampling changes scores from 12.68, 11.30, 12.65 (sample model)
            pairs = list(zip(documents, labels))
            rng.shuffle(pairs)
            documents, labels = list(zip(*pairs))

            # reduce size of dataset to not have too large datasets in the clustering task
            documents_batched = list(batched(documents, 512))[:4]
            labels_batched = list(batched(labels, 512))[:4]
            # See:
            # https://github.com/KennethEnevoldsen/scandinavian-embedding-benchmark/pull/96
            # for a discussion on sizes

            ds[split] = datasets.Dataset.from_dict(
                {
                    "sentences": documents_batched,
                    "labels": labels_batched,
                }
            )

        self.dataset = datasets.DatasetDict(ds)

    @staticmethod
    def normalize_labels(labels: list[str]) -> list[str]:
        # Agreed on and debated in: https://github.com/KennethEnevoldsen/scandinavian-embedding-benchmark/issues/83
        return [label.split(",")[0] for label in labels]
