/* SPDX-License-Identifier: Apache-2.0 */
#pragma once

#include <algorithm>
#include <array>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <filesystem>
#include <fstream>
#include <limits>
#include <new>
#include <string>
#include <type_traits>
#include <vector>

namespace framepipe {

// One aligned, motion-free top-level BVH reference before the builder reorders it.
// Object references have prim_index == -1. Indices are Cycles indices, not Blender IDs.
struct SnapshotRef {
  std::array<float, 3> lo;
  std::array<float, 3> hi;
  std::int32_t prim_index;
  std::int32_t prim_object;
  std::int32_t prim_type;
  std::uint32_t visibility;
};

static_assert(std::is_trivially_copyable_v<SnapshotRef>);
static_assert(sizeof(SnapshotRef) == 40 && std::numeric_limits<float>::is_iec559);

inline bool finite_coordinate(float value)
{
  // The production renderer compiles with /fp:fast. Inspect the exponent to reject
  // malformed cache input even when the optimizer assumes floating values are finite.
  std::uint32_t bits;
  std::memcpy(&bits, &value, sizeof(bits));
  return (bits & 0x7f800000u) != 0x7f800000u;
}

inline bool valid_snapshot_ref(const SnapshotRef &ref)
{
  if (ref.prim_object < 0 || ref.prim_index < -1) {
    return false;
  }
  for (size_t axis = 0; axis < 3; ++axis) {
    if (!finite_coordinate(ref.lo[axis]) || !finite_coordinate(ref.hi[axis]) ||
        ref.lo[axis] > ref.hi[axis]) {
      return false;
    }
  }
  return true;
}

inline bool same_identity(const SnapshotRef &left, const SnapshotRef &right)
{
  return left.prim_index == right.prim_index && left.prim_object == right.prim_object &&
         left.prim_type == right.prim_type;
}

inline bool same_input(const SnapshotRef &left, const SnapshotRef &right)
{
  // No padding (see size assertion above). Bitwise comparison includes bounds and visibility.
  return std::memcmp(&left, &right, sizeof(SnapshotRef)) == 0;
}

namespace snapshot_format {
inline constexpr std::array<char, 8> signature = {'C', 'F', 'B', 'V', 'H', '0', '0', '1'};
inline constexpr std::uintmax_t header_size = signature.size() + sizeof(std::uint64_t);
inline bool supported_host()
{
  const std::uint32_t one = 1;
  return *reinterpret_cast<const unsigned char *>(&one) == 1;
}
}  // namespace snapshot_format

// A cache file is only a prediction. The consumer must still match the references or refit
// every leaf and parent with current data before using the tree for tracing.
inline bool read_snapshot(const std::filesystem::path &path,
                          const std::size_t max_refs,
                          std::vector<SnapshotRef> &out)
{
  out.clear();
  if (path.empty() || !snapshot_format::supported_host()) {
    return false;
  }
  std::error_code error;
  const auto file_size = std::filesystem::file_size(path, error);
  if (error || file_size < snapshot_format::header_size) {
    return false;
  }
  std::ifstream input(path, std::ios::binary);
  std::array<char, 8> signature{};
  std::uint64_t count = 0;
  if (!input.read(signature.data(), signature.size()) ||
      signature != snapshot_format::signature ||
      !input.read(reinterpret_cast<char *>(&count), sizeof(count)) || count > max_refs ||
      count > out.max_size() ||
      count > std::uint64_t(std::numeric_limits<std::streamsize>::max()) / sizeof(SnapshotRef)) {
    return false;
  }
  const auto bytes = count * sizeof(SnapshotRef);
  if (bytes != file_size - snapshot_format::header_size) {
    return false;
  }
  try {
    out.resize(static_cast<std::size_t>(count));
  }
  catch (const std::bad_alloc &) {
    return false;
  }
  if ((bytes && !input.read(reinterpret_cast<char *>(out.data()), std::streamsize(bytes))) ||
      !std::all_of(out.begin(), out.end(), valid_snapshot_ref)) {
    out.clear();
    return false;
  }
  return true;
}

inline bool write_snapshot(const std::filesystem::path &path,
                           const std::vector<SnapshotRef> &refs)
{
  if (path.empty() || !snapshot_format::supported_host() ||
      refs.size() > std::uint64_t(std::numeric_limits<std::streamsize>::max()) /
                        sizeof(SnapshotRef) ||
      !std::all_of(refs.begin(), refs.end(), valid_snapshot_ref)) {
    return false;
  }
  const std::uint64_t count = refs.size();
  // Claim a distinct sibling directory atomically, including when two render jobs share a cache.
  const auto stamp = std::chrono::steady_clock::now().time_since_epoch().count();
  std::filesystem::path temp_dir;
  std::error_code error;
  bool acquired = false;
  for (int attempt = 0; attempt < 8 && !acquired; ++attempt) {
    temp_dir = path;
    temp_dir += ".tmp-" + std::to_string(stamp) + "-" + std::to_string(attempt);
    acquired = std::filesystem::create_directory(temp_dir, error);
    if (error) {
      return false;
    }
  }
  if (!acquired) {
    return false;
  }
  const auto temp_file = temp_dir / "data";
  std::ofstream output(temp_file, std::ios::binary);
  output.write(snapshot_format::signature.data(), snapshot_format::signature.size());
  output.write(reinterpret_cast<const char *>(&count), sizeof(count));
  if (!refs.empty()) {
    output.write(reinterpret_cast<const char *>(refs.data()),
                 std::streamsize(refs.size() * sizeof(SnapshotRef)));
  }
  output.close();
  bool published = false;
  if (output) {
    std::filesystem::rename(temp_file, path, error);
    published = !error;
  }
  std::filesystem::remove(temp_file, error);
  std::filesystem::remove(temp_dir, error);
  return published;
}

}  // namespace framepipe
