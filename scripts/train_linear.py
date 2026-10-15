"""Fit/freeze or independently evaluate the preregistered R3 model; never overwrite."""
import argparse
from ucl.training import LinearTrainer, TrainingSpec, evaluate_frozen

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('operation', choices=('fit', 'test'))
p.add_argument('--dataset', default='experiments/results/r3-data-v2/manifest.json')
p.add_argument('--splits', default='experiments/results/r3-data-v2/splits.json')
p.add_argument('--features', default='experiments/results/r3-features-v2/manifest.json')
p.add_argument('--output', required=True)
a = p.parse_args()
if a.operation == 'fit':
    print(LinearTrainer(a.features).fit(TrainingSpec(a.dataset, 'handcrafted-v1', 20261015, 'white-game-result', a.splits), a.output))
else:
    print(evaluate_frozen(a.output + '/model-manifest.json', a.features))
