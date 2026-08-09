
function parseCard(s){
  s = s.trim();
  var suitMap = {'♠':0,'♥':1,'♦':2,'♣':3};
  var rankMap = {'3':3,'4':4,'5':5,'6':6,'7':7,'8':8,'9':9,'10':10,'J':11,'Q':12,'K':13,'A':14,'2':15,'小王':16,'大王':17};
  if (s === '小王') return {suit:-1, rank:16};
  if (s === '大王') return {suit:-2, rank:17};
  var suitChar = s.slice(-1);
  var rankStr = s.slice(0,-1);
  if (rankMap[rankStr] === undefined) return null;
  return {suit: suitMap[suitChar]!==undefined?suitMap[suitChar]:0, rank: rankMap[rankStr]};
}

var tests = [
  ['3♠', 3], ['10♥', 10], ['J♦', 11], ['Q♣', 12], ['K♠', 13],
  ['A♥', 14], ['2♦', 15], ['小王', 16], ['大王', 17]
];
var pass = 0, fail = 0;
tests.forEach(function(t){
  var r = parseCard(t[0]);
  var ok = r && r.rank === t[1];
  if (ok) pass++; else { fail++; console.log('FAIL: ' + t[0] + ' expected ' + t[1] + ', got ' + (r ? r.rank : 'null')); }
});
console.log('通过 ' + pass + ' / ' + tests.length);
if (fail > 0) { console.log('有失败项！'); }
else { console.log('全部通过！'); }
