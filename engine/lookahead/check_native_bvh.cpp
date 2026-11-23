/* SPDX-License-Identifier: Apache-2.0 */
// Native reference-level test. Links the same BVHFrameLookahead and BVHBuild sources as Cycles.
#include "bvh/build.h"
#include "bvh/frame_lookahead.h"
#include "bvh/node.h"
#include "util/progress.h"

#include <algorithm>
#include <chrono>
#include <cstdio>
#include <stdexcept>
#include <thread>

using namespace ccl;
using Clock = std::chrono::steady_clock;

static void require(bool pass, const char *message)
{
  if (!pass) {
    throw std::runtime_error(message);
  }
}

static BoundBox primitive_box(const int i, const int frame)
{
  const float x = float((i * 37) % 199) + float(frame) * (1.0f + (i % 5) * 0.125f);
  const float y = float((i * 59) % 211) - float(frame) * 0.25f;
  const float z = float((i * 31) % 101) + float(frame) * (i % 3);
  const float3 p = make_float3(x, y, z);
  return BoundBox(p, p + make_float3(0.125f, 0.25f, 0.5f));
}

static uint mask(const int frame)
{
  return frame % 2 == 0 ? 0x12u : 0x21u;
}

class ReferenceBuilder : public BVHBuild {
 public:
  using BVHBuild::BVHBuild;
  BVHRange populate(int count, int frame)
  {
    snapshot_visibility.push_back(mask(frame));
    BoundBox bounds = BoundBox::empty, centers = BoundBox::empty;
    references.reserve(count);
    for (int i = 0; i < count; ++i) {
      const BoundBox b = primitive_box(i, frame);
      references.emplace_back(b, i, 0, PRIMITIVE_TRIANGLE);
      bounds.grow(b);
      centers.grow(b.center2());
    }
    return BVHRange(bounds, centers, 0, count);
  }
  using BVHBuild::build_references;
};

struct FrameBuild {
  vector<Object *> objects;
  array<int> type, index, object;
  array<float2> time;
  Progress progress;
  ReferenceBuilder builder;
  BVHRange range;
  FrameBuild(const BVHParams &params, int count, int frame)
      : builder(objects, type, index, object, time, params, progress),
        range(builder.populate(count, frame))
  {}
};

static BoundBox verify(const BVHNode &node, const FrameBuild &build, int frame,
                       std::vector<unsigned char> &seen)
{
  BoundBox expected = BoundBox::empty;
  if (node.is_leaf()) {
    const auto &leaf = static_cast<const LeafNode &>(node);
    for (int slot = leaf.lo; slot < leaf.hi; ++slot) {
      require(slot >= 0 && size_t(slot) < build.index.size(), "Leaf slot outside packed array");
      int i = build.index[slot];
      require(i >= 0 && size_t(i) < seen.size() && !seen[i], "Missing/duplicate primitive");
      require(build.type[slot] == PRIMITIVE_TRIANGLE && build.object[slot] == 0, "Wrong primitive");
      seen[i] = 1;
      expected.grow(primitive_box(i, frame));
    }
  }
  else {
    for (int c = 0; c < node.num_children(); ++c) {
      expected.grow(verify(*node.get_child(c), build, frame, seen));
    }
  }
  require(node.visibility == mask(frame), "Stale visibility");
  for (int d = 0; d < 3; ++d) {
    require(node.bounds.min[d] == expected.min[d] && node.bounds.max[d] == expected.max[d],
            "Stale node bounds");
  }
  return expected;
}

static double milliseconds(Clock::time_point begin)
{
  return std::chrono::duration<double, std::milli>(Clock::now() - begin).count();
}

int main(int argc, char **argv)
{
  const int count = argc > 1 ? std::stoi(argv[1]) : 50000;
  const int window = argc > 2 ? std::stoi(argv[2]) : 1000;
  require(count > 0 && count < 400000 && window > 0, "Use 1..399999 references, positive gap (ms)");
  TaskScheduler::init(4);
  BVHParams params;
  params.top_level = true;
  params.use_unaligned_nodes = false;
  params.use_spatial_split = false;
  std::vector<double> direct_ms, adoption_ms;
  {
    BVHFrameLookahead pipeline;
    for (int frame = 0; frame < 6; ++frame) {
      const int refs = count + (frame == 5);
      FrameBuild live(params, refs, frame);
      auto start = Clock::now();
      unique_ptr<BVHNode> adopted = pipeline.exchange(live.builder);
      const double exchange_ms = milliseconds(start);
      require(bool(adopted) == (frame > 0 && frame < 5), "Unexpected adoption/miss; see FRAMEPIPE_BVH log");
      if (adopted) {
        std::vector<unsigned char> seen(refs, 0);
        verify(*adopted, live, frame, seen);
        require(std::find(seen.begin(), seen.end(), 0) == seen.end(), "Incomplete refitted tree");
        adoption_ms.push_back(exchange_ms);
      }
      // Independent native synchronous build on exactly the same live references.
      FrameBuild sync(params, refs, frame);
      start = Clock::now();
      auto reference = sync.builder.build_references(sync.range);
      const double sync_ms = milliseconds(start);
      require(bool(reference), "Synchronous BVH build failed");
      if (adopted) {
        direct_ms.push_back(sync_ms);
      }
      else {
        // Exercise the same actual fallback builder that follows a null exchange in run().
        auto fallback = live.builder.build_references(live.range);
        require(bool(fallback), "Native fallback failed");
        std::vector<unsigned char> seen(refs, 0);
        verify(*fallback, live, frame, seen);
        require(std::find(seen.begin(), seen.end(), 0) == seen.end(), "Incomplete fallback tree");
      }
      std::printf("frame=%d refs=%d hit=%d foreground_exchange_ms=%.3f sync_build_ms=%.3f\n",
                  frame, refs, int(bool(adopted)), exchange_ms, sync_ms);
      if (frame < 5) {
        // Represents time available during rendering. It is outside *both* timing measurements.
        pipeline.start();
        std::this_thread::sleep_for(std::chrono::milliseconds(window));
      }
    }
  }
  TaskScheduler::exit();
  auto median = [](std::vector<double> times) {
    std::sort(times.begin(), times.end());
    return (times[1] + times[2]) / 2.0;
  };
  std::printf("median_four_frames refs=%d native_sync_ms=%.3f native_exchange_refit_ms=%.3f\n",
              count, median(direct_ms), median(adoption_ms));
}
