"""
Common utilities for the course experience, including course outline.
"""


from completion.models import BlockCompletion
from opaque_keys.edx.keys import CourseKey
from six.moves import range

from lms.djangoapps.course_api.blocks.api import get_blocks
from lms.djangoapps.course_blocks.utils import get_student_module_as_dict
from openedx.core.lib.cache_utils import request_cached
from xmodule.modulestore.django import modulestore


@request_cached()
def get_course_outline_block_tree(request, course_id, user=None):
    """
    Returns the root block of the course outline, with children as blocks.
    """

    assert user is None or user.is_authenticated

    def populate_children(block, all_blocks):
        """
        Replace each child id with the full block for the child.

        Given a block, replaces each id in its children array with the full
        representation of that child, which will be looked up by id in the
        passed all_blocks dict. Recursively do the same replacement for children
        of those children.
        """
        children = block.get('children', [])

        for i in range(len(children)):
            child_id = block['children'][i]
            child_detail = populate_children(all_blocks[child_id], all_blocks)
            block['children'][i] = child_detail

        return block

    def set_last_accessed_default(block):
        """
        Set default of False for resume_block on all blocks.
        """
        block['resume_block'] = False
        block['complete'] = False
        for child in block.get('children', []):
            set_last_accessed_default(child)

    def mark_blocks_completed(block, user, course_key):
        """
        Walk course tree, marking block completion.
        Mark 'most recent completed block as 'resume_block'

        """
        last_completed_child_position = BlockCompletion.get_latest_block_completed(user, course_key)

        if last_completed_child_position:
            # Mutex w/ NOT 'course_block_completions'
            recurse_mark_complete(
                course_block_completions=BlockCompletion.get_learning_context_completions(user, course_key),
                latest_completion=last_completed_child_position,
                block=block
            )

    def recurse_mark_complete(course_block_completions, latest_completion, block):
        """
        Helper function to walk course tree dict,
        marking blocks as 'complete' and 'last_complete'

        If all blocks are complete, mark parent block complete
        mark parent blocks of 'last_complete' as 'last_complete'

        :param course_block_completions: dict[course_completion_object] =  completion_value
        :param latest_completion: course_completion_object
        :param block: course_outline_root_block block object or child block

        :return:
            block: course_outline_root_block block object or child block
        """
        block_key = block.serializer.instance

        if course_block_completions.get(block_key):
            block['complete'] = True
            if block_key == latest_completion.full_block_key:
                block['resume_block'] = True

        if block.get('children'):
            for idx in range(len(block['children'])):
                recurse_mark_complete(
                    course_block_completions,
                    latest_completion,
                    block=block['children'][idx]
                )
                if block['children'][idx].get('resume_block') is True:
                    block['resume_block'] = True

            completable_blocks = [child for child in block['children']
                                  if child.get('type') != 'discussion']
            if all(child.get('complete') for child in completable_blocks):
                block['complete'] = True

    def mark_last_accessed(user, course_key, block):
        """
        Recursively marks the branch to the last accessed block.
        """
        block_key = block.serializer.instance
        student_module_dict = get_student_module_as_dict(user, course_key, block_key)

        last_accessed_child_position = student_module_dict.get('position')
        if last_accessed_child_position and block.get('children'):
            block['resume_block'] = True
            if last_accessed_child_position <= len(block['children']):
                last_accessed_child_block = block['children'][last_accessed_child_position - 1]
                last_accessed_child_block['resume_block'] = True
                mark_last_accessed(user, course_key, last_accessed_child_block)
            else:
                # We should be using an id in place of position for last accessed.
                # However, while using position, if the child block is no longer accessible
                # we'll use the last child.
                block['children'][-1]['resume_block'] = True

    def recurse_mark_scored(block):
        """
        Mark this block as 'scored' if any of its descendents are 'scored' (that is, 'has_score' and 'weight' > 0).
        """
        is_scored = block.get('has_score', False) and block.get('weight', 1) > 0
        # Use a list comprehension to force the recursion over all children, rather than just stopping
        # at the first child that is scored.
        children_scored = any([recurse_mark_scored(child) for child in block.get('children', [])])
        if is_scored or children_scored:
            block['scored'] = True
            return True
        else:
            block['scored'] = False
            return False

    def recurse_mark_auth_denial(block):
        """
        Mark this block as 'scored' if any of its descendents are 'scored' (that is, 'has_score' and 'weight' > 0).
        """
        own_denial_reason = {block['authorization_denial_reason']} if 'authorization_denial_reason' in block else set()
        # Use a list comprehension to force the recursion over all children, rather than just stopping
        # at the first child that is scored.
        child_denial_reasons = own_denial_reason.union(
            *(recurse_mark_auth_denial(child) for child in block.get('children', []))
        )
        if child_denial_reasons:
            block['all_denial_reasons'] = child_denial_reasons
        return child_denial_reasons

    course_key = CourseKey.from_string(course_id)
    course_usage_key = modulestore().make_course_usage_key(course_key)

    # Deeper query for course tree traversing/marking complete
    # and last completed block
    block_types_filter = [
        'course',
        'chapter',
        'sequential',
        'vertical',
        'html',
        'problem',
        'video',
        'discussion',
        'drag-and-drop-v2',
        'poll',
        'word_cloud'
    ]
    all_blocks = get_blocks(
        request,
        course_usage_key,
        user=request.user,
        nav_depth=3,
        requested_fields=[
            'children',
            'display_name',
            'type',
            'due',
            'graded',
            'has_score',
            'weight',
            'special_exam_info',
            'show_gated_sections',
            'format'
        ],
        block_types_filter=block_types_filter
    )

    course_outline_root_block = all_blocks['blocks'].get(all_blocks['root'], None)
    if course_outline_root_block:
        populate_children(course_outline_root_block, all_blocks['blocks'])
        recurse_mark_scored(course_outline_root_block)
        recurse_mark_auth_denial(course_outline_root_block)
        if user:
            set_last_accessed_default(course_outline_root_block)
            mark_blocks_completed(
                block=course_outline_root_block,
                user=request.user,
                course_key=course_key
            )
    return course_outline_root_block


def get_resume_block(block):
    """
    Gets the deepest block marked as 'resume_block'.

    """
    if block.get('authorization_denial_reason') or not block['resume_block']:
        return None
    if not block.get('children'):
        return block

    for child in block['children']:
        resume_block = get_resume_block(child)
        if resume_block:
            return resume_block
    print('Resume block is: {}'.format(block))
    return block
