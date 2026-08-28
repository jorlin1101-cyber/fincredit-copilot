// This project was developed with assistance from AI tools.

// MVP: client-side lookup for staff display names. Keycloak user IDs are
// deterministic in the seed data so we can resolve them without an API call.
// In production this would be replaced by a user directory lookup.

export const STAFF_NAMES: Record<string, string> = {
  // Borrower demo user
  'd1a2b3c4-e5f6-7890-abcd-ef1234567801': '李晓雨',
  // Loan Officers
  'd1a2b3c4-e5f6-7890-abcd-ef1234567802': '王晨',
  'd1a2b3c4-e5f6-7890-abcd-ef1234567807': '刘欣',
  'd1a2b3c4-e5f6-7890-abcd-ef1234567808': '赵凯',
  // Underwriters
  'd1a2b3c4-e5f6-7890-abcd-ef1234567803': '陈静',
  'd1a2b3c4-e5f6-7890-abcd-ef1234567804': '周明远',
  // Admin
  'd1a2b3c4-e5f6-7890-abcd-ef1234567805': '系统管理员',
  // Borrowers
  'd1a2b3c4-e5f6-7890-abcd-ef1234567806': '李晓雯',
  'd1a2b3c4-e5f6-7890-abcd-ef1234567811': '王志远',
  'd1a2b3c4-e5f6-7890-abcd-ef1234567812': '陈静怡',
  'd1a2b3c4-e5f6-7890-abcd-ef1234567813': '刘浩然',
  'd1a2b3c4-e5f6-7890-abcd-ef1234567814': '赵欣怡',
  'd1a2b3c4-e5f6-7890-abcd-ef1234567815': '周宇航',
  'd1a2b3c4-e5f6-7890-abcd-ef1234567816': '孙雨桐',
  'd1a2b3c4-e5f6-7890-abcd-ef1234567817': '吴子轩',
  'd1a2b3c4-e5f6-7890-abcd-ef1234567818': '郑思琪',
};

export function staffName(userId: string | null | undefined): string {
  if (!userId) return '--';
  return STAFF_NAMES[userId] ?? userId.slice(0, 8);
}
