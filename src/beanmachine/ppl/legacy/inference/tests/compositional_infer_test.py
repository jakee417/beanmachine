# Copyright (c) Meta Platforms, Inc. and affiliates.
#
# This source code is licensed under the MIT license found in the
# LICENSE file in the root directory of this source tree.

import unittest

import beanmachine.ppl as bm
import torch.distributions as dist
from beanmachine.ppl.legacy.inference import CompositionalInference
from beanmachine.ppl.legacy.inference.proposer.single_site_ancestral_proposer import (
    SingleSiteAncestralProposer,
)
from beanmachine.ppl.legacy.inference.proposer.single_site_hamiltonian_monte_carlo_proposer import (
    SingleSiteHamiltonianMonteCarloProposer,
)
from beanmachine.ppl.legacy.inference.proposer.single_site_newtonian_monte_carlo_proposer import (
    SingleSiteNewtonianMonteCarloProposer,
)
from beanmachine.ppl.legacy.inference.proposer.single_site_uniform_proposer import (
    SingleSiteUniformProposer,
)
from beanmachine.ppl.legacy.inference.utils import Block, BlockType
from beanmachine.ppl.legacy.world import TransformType, Variable, World
from beanmachine.ppl.world.utils import BetaDimensionTransform, get_default_transforms
from torch import tensor


class CompositionalInferenceTest(unittest.TestCase):
    class SampleModel(object):
        @bm.random_variable
        def foo(self):
            return dist.Normal(tensor(0.0), tensor(1.0))

        @bm.random_variable
        def foobar(self):
            return dist.Categorical(tensor([0.5, 0, 5]))

        @bm.random_variable
        def foobaz(self):
            return dist.Bernoulli(0.1)

        @bm.random_variable
        def bazbar(self):
            return dist.Poisson(tensor([4]))

    class SampleNormalModel(object):
        @bm.random_variable
        def foo(self, i):
            return dist.Normal(tensor(2.0), tensor(2.0))

        @bm.random_variable
        def bar(self, i):
            return dist.Normal(tensor(10.0), tensor(1.0))

        @bm.random_variable
        def foobar(self, i):
            return dist.Normal(self.foo(i) + self.bar(i), tensor(1.0))

    class SampleTransformModel(object):
        @bm.random_variable
        def realspace(self):
            return dist.Normal(tensor(0.0), tensor(1.0))

        @bm.random_variable
        def halfspace(self):
            return dist.Gamma(tensor(2.0), tensor(2.0))

        @bm.random_variable
        def simplex(self):
            return dist.Dirichlet(tensor([0.1, 0.9]))

        @bm.random_variable
        def interval(self):
            return dist.Uniform(tensor(1.0), tensor(3.0))

        @bm.random_variable
        def beta(self):
            return dist.Beta(tensor(1.0), tensor(1.0))

        @bm.random_variable
        def discrete(self):
            return dist.Poisson(tensor(2.0))

    def test_single_site_compositional_inference(self):
        model = self.SampleModel()
        c = CompositionalInference()
        foo_key = model.foo()
        c.world_ = World()
        distribution = dist.Bernoulli(0.1)
        val = distribution.sample()
        world_vars = c.world_.variables_.vars()
        world_vars[foo_key] = Variable(
            distribution=distribution,
            value=val,
            log_prob=distribution.log_prob(val),
            transformed_value=val,
            jacobian=tensor(0.0),
        )
        self.assertEqual(
            isinstance(
                c.find_best_single_site_proposer(foo_key), SingleSiteUniformProposer
            ),
            True,
        )

        c.proposers_per_rv_ = {}
        distribution = dist.Normal(tensor(0.0), tensor(1.0))
        val = distribution.sample()
        world_vars[foo_key] = Variable(
            distribution=distribution,
            value=val,
            log_prob=distribution.log_prob(val),
            transformed_value=val,
            jacobian=tensor(0.0),
        )

        self.assertEqual(
            isinstance(
                c.find_best_single_site_proposer(foo_key),
                SingleSiteNewtonianMonteCarloProposer,
            ),
            True,
        )

        c.proposers_per_rv_ = {}
        distribution = dist.Categorical(tensor([0.5, 0, 5]))
        val = distribution.sample()
        world_vars[foo_key] = Variable(
            distribution=distribution,
            value=val,
            log_prob=distribution.log_prob(val),
            transformed_value=val,
            jacobian=tensor(0.0),
        )

        self.assertEqual(
            isinstance(
                c.find_best_single_site_proposer(foo_key), SingleSiteUniformProposer
            ),
            True,
        )

        c.proposers_per_rv_ = {}
        distribution = dist.Poisson(tensor([4.0]))
        val = distribution.sample()
        world_vars[foo_key] = Variable(
            distribution=distribution,
            value=val,
            log_prob=distribution.log_prob(val),
            transformed_value=val,
            jacobian=tensor(0.0),
        )
        self.assertEqual(
            isinstance(
                c.find_best_single_site_proposer(foo_key), SingleSiteAncestralProposer
            ),
            True,
        )

    def test_single_site_compositional_inference_with_input(self):
        model = self.SampleModel()
        c = CompositionalInference({model.foo: SingleSiteAncestralProposer()})
        foo_key = model.foo()
        c.world_ = World()
        distribution = dist.Normal(0.1, 1)
        val = distribution.sample()

        world_vars = c.world_.variables_.vars()
        world_vars[foo_key] = Variable(
            distribution=distribution,
            value=val,
            log_prob=distribution.log_prob(val),
            transformed_value=val,
            jacobian=tensor(0.0),
        )
        self.assertEqual(
            isinstance(
                c.find_best_single_site_proposer(foo_key), SingleSiteAncestralProposer
            ),
            True,
        )

    def test_proposer_for_block(self):
        model = self.SampleNormalModel()
        ci = CompositionalInference()
        ci.add_sequential_proposer([model.foo, model.bar])
        ci.queries_ = [
            model.foo(0),
            model.foo(1),
            model.foo(2),
            model.bar(0),
            model.bar(1),
            model.bar(2),
        ]
        ci.observations_ = {
            model.foobar(0): tensor(0.0),
            model.foobar(1): tensor(0.1),
            model.foobar(2): tensor(0.11),
        }

        foo_0_key = model.foo(0)
        foo_1_key = model.foo(1)
        foo_2_key = model.foo(2)
        bar_0_key = model.bar(0)
        foobar_0_key = model.foobar(0)

        ci._infer(2)
        blocks = ci.process_blocks()
        self.assertEqual(len(blocks), 9)
        first_nodes = []
        for block in blocks:
            if block.type == BlockType.SEQUENTIAL:
                first_nodes.append(block.first_node)
                self.assertEqual(
                    block.block,
                    [foo_0_key.wrapper, bar_0_key.wrapper],
                )
            if block.type == BlockType.SINGLENODE:
                self.assertEqual(block.block, [])

        self.assertTrue(foo_0_key in first_nodes)
        self.assertTrue(foo_1_key in first_nodes)
        self.assertTrue(foo_2_key in first_nodes)

        nodes_log_updates, children_log_updates, _ = ci.block_propose_change(
            Block(
                first_node=foo_0_key,
                type=BlockType.SEQUENTIAL,
                block=[foo_0_key.wrapper, bar_0_key.wrapper],
            )
        )

        diff_level_1 = ci.world_.diff_stack_.diff_stack_[-2]
        diff_level_2 = ci.world_.diff_stack_.diff_stack_[-1]

        self.assertEqual(diff_level_1.contains_node(foo_0_key), True)
        self.assertEqual(diff_level_1.contains_node(foobar_0_key), True)
        self.assertEqual(diff_level_2.contains_node(bar_0_key), True)
        self.assertEqual(diff_level_2.contains_node(foobar_0_key), True)

        expected_node_log_updates = (
            ci.world_.diff_stack_.get_node(foo_0_key).log_prob
            - ci.world_.variables_.get_node(foo_0_key).log_prob
        )

        expected_node_log_updates += (
            ci.world_.diff_stack_.get_node(bar_0_key).log_prob
            - ci.world_.variables_.get_node(bar_0_key).log_prob
        )

        expected_children_log_updates = (
            ci.world_.diff_stack_.get_node(foobar_0_key).log_prob
            - ci.world_.variables_.get_node(foobar_0_key).log_prob
        )

        self.assertAlmostEqual(
            expected_node_log_updates.item(), nodes_log_updates.item(), delta=0.001
        )
        self.assertAlmostEqual(
            expected_children_log_updates.item(),
            children_log_updates.item(),
            delta=0.001,
        )

    def test_single_site_compositional_inference_transform_default(self):
        model = self.SampleTransformModel()
        ci = CompositionalInference(
            {
                model.realspace: SingleSiteNewtonianMonteCarloProposer(
                    transform_type=TransformType.DEFAULT
                ),
                model.halfspace: SingleSiteNewtonianMonteCarloProposer(
                    transform_type=TransformType.DEFAULT
                ),
                model.simplex: SingleSiteNewtonianMonteCarloProposer(
                    transform_type=TransformType.DEFAULT
                ),
                model.interval: SingleSiteNewtonianMonteCarloProposer(
                    transform_type=TransformType.DEFAULT
                ),
                model.beta: SingleSiteNewtonianMonteCarloProposer(
                    transform_type=TransformType.DEFAULT
                ),
            }
        )

        queries = [
            model.realspace(),
            model.halfspace(),
            model.simplex(),
            model.interval(),
            model.beta(),
        ]

        ci.queries_ = queries
        ci.observations_ = {}
        ci.initialize_world()
        var_dict = ci.world_.variables_.vars()

        for key in queries:
            self.assertIn(key, var_dict)
            self.assertEqual(
                var_dict[key].transform,
                get_default_transforms(var_dict[key].distribution),
            )

    def test_single_site_compositional_inference_transform_mixed(self):
        model = self.SampleTransformModel()
        ci = CompositionalInference(
            {
                model.realspace: SingleSiteNewtonianMonteCarloProposer(
                    transform_type=TransformType.CUSTOM,
                    transforms=[dist.ExpTransform()],
                ),
                model.halfspace: SingleSiteHamiltonianMonteCarloProposer(
                    0.1, 10, transform_type=TransformType.DEFAULT
                ),
                model.simplex: SingleSiteNewtonianMonteCarloProposer(
                    transform_type=TransformType.NONE
                ),
                model.interval: SingleSiteNewtonianMonteCarloProposer(
                    transform_type=TransformType.CUSTOM,
                    transforms=[dist.AffineTransform(1.0, 2.0)],
                ),
                model.beta: SingleSiteNewtonianMonteCarloProposer(
                    transform_type=TransformType.NONE
                ),
                model.discrete: SingleSiteUniformProposer(
                    transform_type=TransformType.NONE
                ),
            }
        )

        real_key = model.realspace()
        half_key = model.halfspace()
        simplex_key = model.simplex()
        interval_key = model.interval()
        beta_key = model.beta()
        discrete_key = model.discrete()

        ci.queries_ = [
            model.realspace(),
            model.halfspace(),
            model.simplex(),
            model.interval(),
            model.beta(),
            model.discrete(),
        ]
        ci.observations_ = {}
        ci.initialize_world()
        var_dict = ci.world_.variables_.vars()

        self.assertTrue(real_key in var_dict)
        self.assertEqual(
            var_dict[real_key].transform, dist.ComposeTransform([dist.ExpTransform()])
        )

        self.assertTrue(half_key in var_dict)
        self.assertEqual(
            var_dict[half_key].transform,
            get_default_transforms(var_dict[half_key].distribution),
        )

        self.assertTrue(simplex_key in var_dict)
        self.assertEqual(
            var_dict[simplex_key].transform, dist.transforms.identity_transform
        )

        self.assertTrue(interval_key in var_dict)
        self.assertEqual(
            var_dict[interval_key].transform,
            dist.ComposeTransform([dist.AffineTransform(1.0, 2.0)]),
        )

        self.assertTrue(beta_key in var_dict)
        self.assertEqual(
            var_dict[beta_key].transform,
            BetaDimensionTransform(),
        )

        self.assertTrue(discrete_key in var_dict)
        self.assertEqual(
            var_dict[discrete_key].transform, dist.transforms.identity_transform
        )

    def test_single_site_compositional_inference_ancestral_beta(self):
        model = self.SampleTransformModel()
        ci = CompositionalInference(
            {model.beta: SingleSiteAncestralProposer(transform_type=TransformType.NONE)}
        )

        beta_key = model.beta()

        ci.queries_ = [model.beta()]
        ci.observations_ = {}
        ci.initialize_world()
        var_dict = ci.world_.variables_.vars()

        self.assertTrue(beta_key in var_dict)
        self.assertEqual(
            var_dict[beta_key].transform, dist.transforms.identity_transform
        )
