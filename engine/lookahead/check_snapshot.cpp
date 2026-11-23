/* SPDX-License-Identifier: Apache-2.0 */
#include "bvh/frame_snapshot.h"

#include <iostream>
#include <stdexcept>

static void require(bool value, const char *message)
{
  if (!value) {
    throw std::runtime_error(message);
  }
}

#ifdef _WIN32
int wmain(int argc, wchar_t **argv)
#else
int main(int argc, char **argv)
#endif
{
  if (argc != 2) {
    return 2;
  }
  const std::filesystem::path path = std::filesystem::path(argv[1]) / "check.cfbvh";
  std::vector<framepipe::SnapshotRef> original = {
      {{-2, 0, 2}, {1, 5, 3}, 4, 0, 1, 15}, {{4, 0, 1}, {5, 1, 4}, -1, 1, 0, 8}};
  require(framepipe::write_snapshot(path, original), "Could not capture");
  std::vector<framepipe::SnapshotRef> imported;
  require(framepipe::read_snapshot(path, 2, imported) && imported.size() == 2, "Bad import");
  require(framepipe::same_input(original[0], imported[0]), "Bounds or visibility changed");
  imported[0].hi[0] = 2;
  require(framepipe::same_identity(original[0], imported[0]) &&
              !framepipe::same_input(original[0], imported[0]),
          "Moved bounds must require a refit");
  imported[0].prim_object = 1;
  require(!framepipe::same_identity(original[0], imported[0]), "Changed owner must be rejected");
  require(!framepipe::read_snapshot(path, 1, imported) && imported.empty(), "Reference budget");
  std::filesystem::resize_file(path, 16);
  require(!framepipe::read_snapshot(path, 2, imported), "Partial snapshot");
  require(framepipe::write_snapshot(path, original), "Atomic replacement failed");
  original[1].lo[2] = std::numeric_limits<float>::quiet_NaN();
  require(!framepipe::write_snapshot(path, original) && framepipe::read_snapshot(path, 2, imported),
          "A failed capture must preserve the previous snapshot");
  std::cout << "Snapshot round trip, identity, size cap, truncation and replacement passed.\n";
}
