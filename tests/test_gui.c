#include "utest.h"
#include "ext/lib/gui.h"

UTEST(gui, add_child_links_parent_and_child) {
  gui_item *parent, *child;

  parent = GuiGroupNew();
  child = GuiGroupNew();
  GuiAddChild(parent, child);
  ASSERT_TRUE(parent->child == child);
  ASSERT_TRUE(child->parent == parent);
  GuiItemFree(parent, 1);
}

UTEST(gui, remove_node_moves_only_child_to_parent) {
  gui_item *parent, *item, *child;

  parent = GuiGroupNew();
  item = GuiGroupNew();
  child = GuiGroupNew();
  GuiAddChild(parent, item);
  GuiAddChild(item, child);
  GuiRemoveNode(item);
  ASSERT_TRUE(parent->child == child);
  ASSERT_TRUE(child->parent == parent);
  ASSERT_TRUE(child->next == 0);
  GuiItemFree(parent, 1);
}

UTEST(gui, remove_node_without_children) {
  gui_item *parent, *first, *second;

  parent = GuiGroupNew();
  first = GuiGroupNew();
  second = GuiGroupNew();
  GuiAddChild(parent, first);
  GuiAddChild(parent, second);
  GuiRemoveNode(first);
  ASSERT_TRUE(parent->child == second);
  ASSERT_TRUE(second->prev == 0);
  ASSERT_TRUE(second->next == 0);
  GuiItemFree(parent, 1);
}

UTEST(gui, remove_node_moves_every_child_to_parent) {
  gui_item *parent, *to_remove, *child1, *child2, *child3;

  parent = GuiGroupNew();
  to_remove = GuiGroupNew();
  child1 = GuiGroupNew();
  child2 = GuiGroupNew();
  child3 = GuiGroupNew();
  GuiAddChild(parent, to_remove);
  GuiAddChild(to_remove, child1);
  GuiAddChild(to_remove, child2);
  GuiAddChild(to_remove, child3);
  GuiRemoveNode(to_remove);
  /* the children are now the parent's children, in their original order */
  ASSERT_TRUE(parent->child == child1);
  ASSERT_TRUE(child1->next == child2);
  ASSERT_TRUE(child2->next == child3);
  ASSERT_TRUE(child3->next == 0);
  ASSERT_TRUE(child1->parent == parent);
  ASSERT_TRUE(child2->parent == parent);
  ASSERT_TRUE(child3->parent == parent);
  GuiItemFree(parent, 1);
}

UTEST(gui, insert_node_after_sibling) {
  gui_item *parent, *child1, *child2, *to_insert;

  parent = GuiGroupNew();
  child1 = GuiGroupNew();
  child2 = GuiGroupNew();
  to_insert = GuiGroupNew();
  GuiAddChild(parent, child1);
  GuiAddChild(parent, child2);
  GuiInsertNode(parent, child1, to_insert);
  ASSERT_TRUE(parent->child == child1);
  ASSERT_TRUE(child1->next == to_insert);
  ASSERT_TRUE(to_insert->next == child2);
  ASSERT_TRUE(to_insert->prev == child1);
  ASSERT_TRUE(to_insert->parent == parent);
  GuiItemFree(parent, 1);
}

UTEST(gui, insert_node_at_front) {
  gui_item *parent, *child1, *to_insert;

  parent = GuiGroupNew();
  child1 = GuiGroupNew();
  to_insert = GuiGroupNew();
  GuiAddChild(parent, child1);
  GuiInsertNode(parent, 0, to_insert);
  ASSERT_TRUE(parent->child == to_insert);
  ASSERT_TRUE(to_insert->next == child1);
  ASSERT_TRUE(child1->prev == to_insert);
  ASSERT_TRUE(to_insert->parent == parent);
  GuiItemFree(parent, 1);
}

UTEST(gui, insert_node_after_sibling_of_other_parent_appends) {
  gui_item *parent1, *parent2, *child1, *child2, *to_insert;

  parent1 = GuiGroupNew();
  parent2 = GuiGroupNew();
  child1 = GuiGroupNew();
  child2 = GuiGroupNew();
  to_insert = GuiGroupNew();
  GuiAddChild(parent1, child1);
  GuiAddChild(parent2, child2);
  /* child2 is not one of parent1's children */
  GuiInsertNode(parent1, child2, to_insert);
  ASSERT_TRUE(parent1->child == child1);
  ASSERT_TRUE(child1->next == to_insert);
  ASSERT_TRUE(to_insert->next == 0);
  ASSERT_TRUE(to_insert->parent == parent1);
  ASSERT_TRUE(parent1->tail_child == to_insert);
  /* parent2's children are untouched */
  ASSERT_TRUE(parent2->child == child2);
  ASSERT_TRUE(child2->next == 0);
  ASSERT_TRUE(parent2->tail_child == child2);
  GuiItemFree(parent1, 1);
  GuiItemFree(parent2, 1);
}
