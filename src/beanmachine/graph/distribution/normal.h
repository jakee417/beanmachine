/*
 * Copyright (c) Meta Platforms, Inc. and affiliates.
 *
 * This source code is licensed under the MIT license found in the
 * LICENSE file in the root directory of this source tree.
 */

#pragma once
#include "beanmachine/graph/distribution/distribution.h"

namespace beanmachine {
namespace distribution {

class Normal : public Distribution {
 public:
  Normal(
      graph::AtomicType sample_type,
      const std::vector<graph::Node*>& in_nodes);
  ~Normal() override {}
  double _double_sampler(std::mt19937& gen) const override;
  double log_prob(const graph::NodeValue& value) const override;
  void log_prob_iid(const graph::NodeValue& value, Eigen::MatrixXd& log_probs)
      const override;
  void gradient_log_prob_value(
      const graph::NodeValue& value,
      double& grad1,
      double& grad2) const override;
  void gradient_log_prob_param(
      const graph::NodeValue& value,
      double& grad1,
      double& grad2) const override;

  void backward_value(
      const graph::NodeValue& value,
      graph::DoubleMatrix& back_grad,
      double adjunct = 1.0) const override;
  void backward_value_iid(
      const graph::NodeValue& value,
      graph::DoubleMatrix& back_grad) const override;
  void backward_value_iid(
      const graph::NodeValue& value,
      graph::DoubleMatrix& back_grad,
      Eigen::MatrixXd& adjunct) const override;

  void backward_param(const graph::NodeValue& value, double adjunct = 1.0)
      const override;
  void backward_param_iid(const graph::NodeValue& value) const override;
  void backward_param_iid(
      const graph::NodeValue& value,
      Eigen::MatrixXd& adjunct) const override;

  static void
  _grad1_log_prob_value(double& grad1, double val, double m, double s_sq);
};

} // namespace distribution
} // namespace beanmachine
